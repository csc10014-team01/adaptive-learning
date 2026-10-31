"""Run from repository root: python -m uvicorn src.api.main:app --port 8000."""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from src.api.data_adapter import ApiFailure, DEFAULT_BANK, DEFAULT_FIXTURES, StaticDataAdapter
from src.api.schemas import (
    ApiError, ApiErrorResponse, ErrorDetail, ExamResponse, GenerateExamRequest, LEVELS,
    StudentListResponse, StudentProfileResponse, TopicListResponse,
    ApproveExamRequest, RegenerateQuestionRequest,
)
from src.api.services import ExamGenerator, FakeExamGenerator, InMemoryExamStore
from src.adaptation.planner import ExamPlan, RuleBasedPlanner
from src.adaptation.skill_relationships import SkillRelationships
from src.ai.qwen_client import QwenClient
from src.api.exam_store import SQLiteExamStore
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.api.real_generator import QwenExamGenerator
from src.api.data_adapter import ROOT
from src.orchestration.review_service import approve_exam, check_revision, validate_regeneration, require_template_regeneration
from src.ui.routes import mount_ui

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def require_teacher(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    configured = request.app.state.teacher_token
    if not configured:
        raise ApiFailure(503, "TEACHER_ACCESS_NOT_CONFIGURED", "Cần cấu hình API_TEACHER_TOKEN.")
    if credentials is None:
        raise ApiFailure(401, "TEACHER_AUTH_REQUIRED", "Cần teacher bearer token.")
    if not secrets.compare_digest(credentials.credentials.encode(), configured.encode()):
        raise ApiFailure(403, "TEACHER_ACCESS_DENIED", "Không có quyền truy cập teacher API.")


def get_data(request: Request) -> StaticDataAdapter:
    with request.app.state.data_lock:
        if request.app.state.data is None:
            state = request.app.state
            if state.profile_source == "m3" or state.backend == "qwen":
                state.data = M3DataAdapter(student_path=state.student_path, bank_path=state.bank_path,
                    profile_json=state.profile_source == "json", fixture_dir=state.fixture_dir)
            else:
                state.data = StaticDataAdapter(state.fixture_dir, state.bank_path)
        return request.app.state.data


def get_exam_generator(
    request: Request, data: Annotated[StaticDataAdapter, Depends(get_data)],
) -> ExamGenerator:
    state = request.app.state
    if state.generator is not None:
        return state.generator
    if state.backend == "fake":
        return FakeExamGenerator(data, planner=RuleBasedPlanner(data, relationships=state.relationships))
    return QwenExamGenerator(data, state.qwen_client,
        planner=RuleBasedPlanner(data, relationships=state.relationships))


def error_response(status: int, code: str, message: str, details: list[ErrorDetail] | None = None) -> JSONResponse:
    payload = ApiErrorResponse(error=ApiError(code=code, message=message, details=details or []))
    return JSONResponse(
        status_code=status, content=payload.model_dump(mode="json"),
        headers={"Cache-Control": "no-store", **({"WWW-Authenticate": "Bearer"} if status == 401 else {})},
    )


def automatic_exam_request(payload: GenerateExamRequest) -> GenerateExamRequest:
    """One public request policy for preview and both generation backends.

    Old modes/quotas remain readable for internal integrations and old drafts;
    the teacher API never allows them to bypass profile-driven planning.
    """
    issues = []
    if payload.generation_mode != "adaptive":
        issues.append({"loc": ("body", "generation_mode"), "msg": "Chỉ hỗ trợ adaptive: hệ thống tự chọn kế hoạch theo hồ sơ.", "type": "value_error"})
    if payload.difficulty_distribution is not None:
        issues.append({"loc": ("body", "difficulty_distribution"), "msg": "Độ khó được xác định tự động; không chấp nhận tỷ lệ thủ công.", "type": "value_error"})
    if issues:
        raise RequestValidationError(issues)
    return payload


def create_app(
    *, fixture_dir: Path | None = None, bank_path: Path = DEFAULT_BANK,
    teacher_token: str | None = None, generator: ExamGenerator | None = None,
    backend: str | None = None, profile_source: str | None = None,
    student_path: Path | None = None, exam_db: Path | None = None,
    qwen_client: QwenClient | None = None,
    relationships: SkillRelationships | None = None,
) -> FastAPI:
    backend = backend or os.getenv("EXAM_BACKEND", "qwen")
    profile_source = profile_source or os.getenv("PROFILE_SOURCE", "json" if backend == "fake" else "m3")
    if backend not in ("fake", "qwen") or profile_source not in ("json", "m3"):
        raise ValueError("EXAM_BACKEND must be qwen/fake; PROFILE_SOURCE must be m3/json")
    api = FastAPI(title="Smart Exam Generator — Personalized MVP", version="1.1.0")
    api.state.backend, api.state.profile_source = backend, profile_source
    relationship_file = os.getenv("SKILL_RELATIONSHIPS_FILE")
    api.state.relationships = relationships or (SkillRelationships.load(Path(relationship_file)) if relationship_file else None)
    api.state.student_path = student_path or Path(os.getenv("M3_STUDENT_DB", str(DEFAULT_STUDENTS)))
    if not api.state.student_path.is_absolute():
        api.state.student_path = ROOT / api.state.student_path
    api.state.qwen_client = qwen_client or QwenClient(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=os.getenv("QWEN_MODEL", "qwen3:1.7b"),
        timeout=float(os.getenv("QWEN_TIMEOUT_SECONDS", "45")),
        attempts=int(os.getenv("QWEN_MAX_ATTEMPTS", "2")),
        exam_timeout=float(os.getenv("EXAM_TIMEOUT_SECONDS", "180")),
    )
    api.state.teacher_token = teacher_token if teacher_token is not None else (
        os.getenv("API_TEACHER_TOKEN") or os.getenv("FAKE_API_TEACHER_TOKEN"))
    api.state.fixture_dir = fixture_dir or Path(os.getenv(
        "API_PROFILE_DIR", os.getenv("FAKE_API_FIXTURE_DIR", str(DEFAULT_FIXTURES))))
    api.state.bank_path = Path(os.getenv("M3_QUESTION_DB", str(bank_path)))
    if not api.state.bank_path.is_absolute():
        api.state.bank_path = ROOT / api.state.bank_path
    api.state.data = None
    api.state.data_lock = Lock()
    api.state.generator = generator
    store_path = exam_db or Path(os.getenv("EXAM_DB", str(ROOT / "data/runtime/exams.db")))
    if backend == "qwen" and store_path.resolve() in {
        api.state.bank_path.resolve(), api.state.student_path.resolve(),
    }:
        raise ValueError("EXAM_DB must be separate from canonical M3 databases")
    api.state.exams = InMemoryExamStore() if backend == "fake" else SQLiteExamStore(store_path)

    @api.exception_handler(ApiFailure)
    async def handle_failure(request: Request, exc: ApiFailure) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @api.exception_handler(RequestValidationError)
    async def handle_request_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "REQUEST_VALIDATION_ERROR", "Request không hợp lệ.", [
            ErrorDetail(field=".".join(map(str, issue["loc"])), reason=issue["msg"])
            for issue in exc.errors()
        ])

    @api.exception_handler(ResponseValidationError)
    async def handle_response_error(request: Request, exc: ResponseValidationError) -> JSONResponse:
        logger.error("Response contract violation at %s", request.url.path)
        return error_response(500, "INVALID_EXAM_OUTPUT", "Service output không đúng contract.")

    @api.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected API failure at %s", request.url.path)
        return error_response(500, "INTERNAL_ERROR", "Backend không thể xử lý request.")

    @api.middleware("http")
    async def private_responses(request: Request, call_next):
        # Return unexpected failures inside the outer CORS middleware too. Letting
        # them escape to ServerErrorMiddleware loses allowed-origin response headers.
        try:
            response = await call_next(request)
        except Exception as exc:
            response = await handle_unexpected_error(request, exc)
        response.headers["Cache-Control"] = "no-store"
        return response

    router = APIRouter(
        prefix="/api/v1", dependencies=[Depends(require_teacher)],
        responses={code: {"model": ApiErrorResponse} for code in (401, 403, 404, 409, 422, 500, 502, 503, 504)},
    )

    @router.get("/students", response_model=StudentListResponse)
    def students(data: Annotated[StaticDataAdapter, Depends(get_data)]) -> StudentListResponse:
        return StudentListResponse(items=data.list_students())

    @router.get("/students/{student_id}/profile", response_model=StudentProfileResponse)
    def profile(student_id: str, data: Annotated[StaticDataAdapter, Depends(get_data)]) -> StudentProfileResponse:
        return data.get_profile(student_id)

    @router.get("/topics", response_model=TopicListResponse)
    def topics(data: Annotated[StaticDataAdapter, Depends(get_data)]) -> TopicListResponse:
        return TopicListResponse(items=[data.topic])

    @router.post("/exams/generate", response_model=ExamResponse)
    def generate(
        payload: Annotated[GenerateExamRequest, Depends(automatic_exam_request)], request: Request,
        data: Annotated[StaticDataAdapter, Depends(get_data)],
        service: Annotated[ExamGenerator, Depends(get_exam_generator)],
    ) -> ExamResponse:
        student = data.get_profile(payload.student_id)
        # Evidence policy belongs to the planner; pass per-skill data unchanged.
        try:
            # The generator receives isolated working copies. Validate against the
            # trusted originals, including nested lists/models, after it returns.
            exam = ExamResponse.model_validate(service.generate(
                payload.model_copy(deep=True), student.model_copy(deep=True),
            ))
            expected = (
                exam.status == "pending_teacher_review" and exam.revision == 1,
                exam.teacher_review is None and all(not q.validation.teacher_approved
                    and not q.validation.blocking_errors for q in exam.questions),
                exam.provenance.generator == "fake" or all(
                    q.validation.auto_status != "not_evaluated" for q in exam.questions),
                exam.student_id == student.student_id,
                exam.grade_level == student.grade_level,
                exam.generation_mode == payload.generation_mode,
                exam.total_questions == payload.total_questions,
                exam.duration_minutes == payload.duration_minutes,
                exam.topic_id == payload.selected_topic_ids[0],
                exam.planner_summary is None or (not exam.planner_summary.difficulty_locked
                    and exam.planner_summary.quota_summary.achieved_levels == {
                        level: sum(q.cognitive_level == level for q in exam.questions)
                        for level in LEVELS}),
            )
            if not all(expected):
                raise ValueError("Service output does not match request/profile")
            data.validate_exam_references(exam)
        except (ValidationError, ValueError) as exc:
            raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Service output không đúng contract.") from exc
        request.app.state.exams.save(exam)
        return exam

    @router.post("/exams/plan", response_model=ExamPlan)
    def plan(payload: Annotated[GenerateExamRequest, Depends(automatic_exam_request)], data: Annotated[StaticDataAdapter, Depends(get_data)]) -> ExamPlan:
        """Preview rule decisions without invoking Qwen or storing a draft."""
        return RuleBasedPlanner(data, relationships=api.state.relationships).plan(payload, data.get_profile(payload.student_id))

    @router.get("/exams/{exam_id}", response_model=ExamResponse)
    def exam(exam_id: str, request: Request) -> ExamResponse:
        return request.app.state.exams.get(exam_id)

    @router.post("/exams/{exam_id}/approve", response_model=ExamResponse)
    def approve(exam_id: str, payload: ApproveExamRequest, request: Request,
                data: Annotated[StaticDataAdapter, Depends(get_data)]) -> ExamResponse:
        store = request.app.state.exams
        current = store.get(exam_id)
        check_revision(current, payload.expected_revision)
        reviewed = approve_exam(current, payload)
        try:
            data.validate_exam_references(reviewed)
        except (ValueError, ValidationError) as exc:
            raise ApiFailure(409, "EXAM_NOT_READY", "Stored source content or Template proof is no longer valid") from exc
        store.replace(reviewed, expected_revision=payload.expected_revision)
        return reviewed

    @router.post("/exams/{exam_id}/questions/{question_id}/regenerate", response_model=ExamResponse)
    def regenerate(exam_id: str, question_id: str, payload: RegenerateQuestionRequest, request: Request,
                   data: Annotated[StaticDataAdapter, Depends(get_data)],
                   service: Annotated[ExamGenerator, Depends(get_exam_generator)]) -> ExamResponse:
        store = request.app.state.exams
        current = store.get(exam_id)
        check_revision(current, payload.expected_revision)
        require_template_regeneration(current, question_id)
        if not hasattr(service, "regenerate_question"):
            raise ApiFailure(409, "REGENERATION_UNSUPPORTED", "Regeneration requires the Qwen pipeline")
        regenerated = ExamResponse.model_validate(service.regenerate_question(current.model_copy(deep=True), question_id))
        validate_regeneration(current, regenerated, question_id, data=data)
        data.validate_exam_references(regenerated)
        store.replace(regenerated, expected_revision=payload.expected_revision)
        return regenerated

    api.include_router(router)
    mount_ui(api, require_teacher)
    # Registered last so CORS wraps the response/error boundary above.
    origins = [value.strip() for value in (
        os.getenv("API_CORS_ORIGINS") or os.getenv("FAKE_API_CORS_ORIGINS", "")
    ).split(",") if value.strip()]
    if origins:
        api.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    return api


app = create_app()
