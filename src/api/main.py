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

from src.api.adaptive_generator import (
    AdaptiveExamGenerator,
    SQLDataAdapter,
    core_data,
    core_exam,
    public_exam,
)
from src.api.data_adapter import (
    DEFAULT_BANK,
    DEFAULT_FIXTURES,
    ROOT,
    ApiFailure,
    StaticDataAdapter,
)
from src.api.exam_store import SQLiteExamStore
from src.api.schemas import (
    ApiError,
    ApiErrorResponse,
    ApproveExamRequest,
    ErrorDetail,
    ExamResponse,
    GenerateExamRequest,
    RegenerateQuestionRequest,
    StudentListResponse,
    StudentProfileResponse,
    TopicListResponse,
)
from src.api.services import (
    ExamGenerator,
    FakeExamGenerator,
    InMemoryExamStore,
    question_slots,
)
from src.exam_generator.adaptation.planner import ExamPlan
from src.exam_generator.adaptation.skill_relationships import SkillRelationships
from src.exam_generator.ai.qwen_client import QwenClient
from src.exam_generator.api.data_adapter import ApiFailure as CoreApiFailure
from src.exam_generator.api.m3_adapter import DEFAULT_STUDENTS
from src.exam_generator.orchestration.review_service import (
    approve_exam,
    check_revision,
    require_template_regeneration,
    validate_regeneration,
)
from src.ui.routes import mount_ui

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def require_teacher(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    configured = request.app.state.teacher_token
    if not configured:
        raise ApiFailure(
            503, "TEACHER_ACCESS_NOT_CONFIGURED", "Cần cấu hình FAKE_API_TEACHER_TOKEN."
        )
    if credentials is None:
        raise ApiFailure(401, "TEACHER_AUTH_REQUIRED", "Cần teacher bearer token.")
    if not secrets.compare_digest(
        credentials.credentials.encode(), configured.encode()
    ):
        raise ApiFailure(
            403, "TEACHER_ACCESS_DENIED", "Không có quyền truy cập teacher API."
        )


def get_data(request: Request) -> StaticDataAdapter:
    with request.app.state.data_lock:
        if request.app.state.data is None:
            state = request.app.state
            state.data = (
                SQLDataAdapter(
                    fixture_dir=state.fixture_dir,
                    bank_path=state.bank_path,
                    student_path=state.student_path,
                )
                if state.profile_source == "m3"
                else StaticDataAdapter(state.fixture_dir, state.bank_path)
            )
        return request.app.state.data


def get_exam_generator(
    request: Request,
    data: Annotated[StaticDataAdapter, Depends(get_data)],
) -> ExamGenerator:
    state = request.app.state
    if state.generator is not None:
        return state.generator
    return (
        AdaptiveExamGenerator(
            data,
            state.qwen_client,
            fake=state.backend == "fake",
            relationships=state.relationships,
            instance_seed=state.instance_seed,
        )
        if state.backend == "qwen"
        else FakeExamGenerator(data)
    )


def error_response(
    status: int, code: str, message: str, details: list[ErrorDetail] | None = None
) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiError(code=code, message=message, details=details or [])
    )
    return JSONResponse(
        status_code=status,
        content=payload.model_dump(mode="json"),
        headers={
            "Cache-Control": "no-store",
            **({"WWW-Authenticate": "Bearer"} if status == 401 else {}),
        },
    )


def create_app(
    *,
    fixture_dir: Path | None = None,
    bank_path: Path = DEFAULT_BANK,
    teacher_token: str | None = None,
    generator: ExamGenerator | None = None,
    backend: str | None = None,
    profile_source: str | None = None,
    student_path: Path | None = None,
    exam_db: Path | None = None,
    qwen_client: QwenClient | None = None,
    relationships: SkillRelationships | None = None,
    instance_seed: int | None = None,
) -> FastAPI:
    api = FastAPI(title="Smart Exam Generator — Fake MVP1", version="1.0.0")
    # Keep the team's default JSON/fake service; the Generator launcher explicitly
    # selects SQL/Qwen. No missing database can implicitly activate JSON fallback.
    backend = backend or os.getenv("EXAM_BACKEND", "fake")
    profile_source = profile_source or os.getenv(
        "PROFILE_SOURCE", "m3" if backend == "qwen" else "json"
    )
    if backend not in ("fake", "qwen") or profile_source not in ("json", "m3"):
        raise ValueError(
            "EXAM_BACKEND must be fake/qwen; PROFILE_SOURCE must be json/m3"
        )
    api.state.backend, api.state.profile_source = backend, profile_source
    api.state.instance_seed = instance_seed
    relationship_file = os.getenv("SKILL_RELATIONSHIPS_FILE")
    api.state.relationships = relationships or (
        SkillRelationships.load(Path(relationship_file)) if relationship_file else None
    )
    api.state.student_path = student_path or Path(
        os.getenv("M3_STUDENT_DB", str(DEFAULT_STUDENTS))
    )
    if not api.state.student_path.is_absolute():
        api.state.student_path = ROOT / api.state.student_path
    api.state.qwen_client = qwen_client or QwenClient(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=os.getenv("QWEN_MODEL", "qwen3:1.7b"),
        timeout=float(os.getenv("QWEN_TIMEOUT_SECONDS", "45")),
        attempts=int(os.getenv("QWEN_MAX_ATTEMPTS", "2")),
        exam_timeout=float(os.getenv("EXAM_TIMEOUT_SECONDS", "180")),
    )
    api.state.teacher_token = (
        teacher_token
        if teacher_token is not None
        else (os.getenv("API_TEACHER_TOKEN") or os.getenv("FAKE_API_TEACHER_TOKEN"))
    )
    api.state.fixture_dir = fixture_dir or Path(
        os.getenv("FAKE_API_FIXTURE_DIR", str(DEFAULT_FIXTURES))
    )
    api.state.bank_path = Path(os.getenv("M3_QUESTION_DB", str(bank_path)))
    if not api.state.bank_path.is_absolute():
        api.state.bank_path = ROOT / api.state.bank_path
    api.state.data = None
    api.state.data_lock = Lock()
    api.state.generator = generator
    store_path = exam_db or Path(
        os.getenv("EXAM_DB", str(ROOT / "data/runtime/exams.db"))
    )
    if not store_path.is_absolute():
        store_path = ROOT / store_path
    if store_path.resolve() in {
        api.state.bank_path.resolve(),
        api.state.student_path.resolve(),
    }:
        raise ValueError("EXAM_DB must be separate from canonical SQL databases")
    api.state.exams = (
        InMemoryExamStore() if backend == "fake" else SQLiteExamStore(store_path)
    )

    @api.exception_handler(CoreApiFailure)
    @api.exception_handler(ApiFailure)
    async def handle_failure(request: Request, exc: ApiFailure) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @api.exception_handler(RequestValidationError)
    async def handle_request_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            422,
            "REQUEST_VALIDATION_ERROR",
            "Request không hợp lệ.",
            [
                ErrorDetail(field=".".join(map(str, issue["loc"])), reason=issue["msg"])
                for issue in exc.errors()
            ],
        )

    @api.exception_handler(ResponseValidationError)
    async def handle_response_error(
        request: Request, exc: ResponseValidationError
    ) -> JSONResponse:
        logger.error("Response contract violation at %s", request.url.path)
        return error_response(
            500, "INVALID_EXAM_OUTPUT", "Service output không đúng contract."
        )

    @api.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected fake API failure at %s", request.url.path)
        return error_response(500, "INTERNAL_ERROR", "Backend không thể xử lý request.")

    @api.middleware("http")
    async def private_responses(request: Request, call_next):
        # Return unexpected failures inside the outer CORS middleware too. Letting
        # them escape to ServerErrorMiddleware loses allowed-origin response headers.
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 -- Preserve the outer CORS/error response boundary.
            response = await handle_unexpected_error(request, exc)
        response.headers["Cache-Control"] = "no-store"
        return response

    router = APIRouter(
        prefix="/api/v1",
        dependencies=[Depends(require_teacher)],
        responses={
            code: {"model": ApiErrorResponse}
            for code in (401, 403, 404, 409, 422, 500, 502, 503, 504)
        },
    )

    @router.get("/students", response_model=StudentListResponse)
    def students(
        data: Annotated[StaticDataAdapter, Depends(get_data)],
    ) -> StudentListResponse:
        return StudentListResponse(items=data.list_students())

    @router.get("/students/{student_id}/profile", response_model=StudentProfileResponse)
    def profile(
        student_id: str, data: Annotated[StaticDataAdapter, Depends(get_data)]
    ) -> StudentProfileResponse:
        return data.get_profile(student_id)

    @router.get("/topics", response_model=TopicListResponse)
    def topics(
        data: Annotated[StaticDataAdapter, Depends(get_data)],
    ) -> TopicListResponse:
        return TopicListResponse(items=[data.topic])

    @router.post("/exams/generate", response_model=ExamResponse)
    def generate(
        payload: GenerateExamRequest,
        request: Request,
        data: Annotated[StaticDataAdapter, Depends(get_data)],
        service: Annotated[ExamGenerator, Depends(get_exam_generator)],
    ) -> ExamResponse:
        student = data.get_profile(payload.student_id)
        # Adaptive eligibility is decided per skill by the finalized Planner.
        if request.app.state.generator is None:
            state = request.app.state
            service = (
                AdaptiveExamGenerator(
                    data,
                    state.qwen_client,
                    fake=state.backend == "fake",
                    relationships=state.relationships,
                    instance_seed=state.instance_seed,
                )
                if payload.generation_mode == "adaptive"
                else FakeExamGenerator(data)
            )
        try:
            # The generator receives isolated working copies. Validate against the
            # trusted originals, including nested lists/models, after it returns.
            exam = ExamResponse.model_validate(
                service.generate(
                    payload.model_copy(deep=True),
                    student.model_copy(deep=True),
                )
            )
            expected = (
                exam.student_id == student.student_id,
                exam.grade_level == student.grade_level,
                exam.evidence_count == student.evidence_count,
                exam.data_status == student.data_status,
                exam.generation_mode == payload.generation_mode,
                exam.total_questions == payload.total_questions,
                exam.duration_minutes == payload.duration_minutes,
                exam.topic_id == payload.selected_topic_ids[0],
                exam.status == "pending_teacher_review" and exam.revision == 1,
                exam.teacher_review is None
                and all(
                    not q.validation.teacher_approved
                    and not q.validation.blocking_errors
                    for q in exam.questions
                ),
                exam.provenance.generator == "fake"
                or all(
                    q.validation.auto_status != "not_evaluated" for q in exam.questions
                ),
            )
            if not all(expected):
                raise ValueError("Service output does not match request/profile")
            if payload.generation_mode == "adaptive":
                AdaptiveExamGenerator(
                    data, relationships=request.app.state.relationships
                ).validate_output(payload, student, exam)
            else:
                if {
                    level: sum(q.cognitive_level == level for q in exam.questions)
                    for level in question_slots(payload)
                } != question_slots(payload):
                    raise ValueError("Non-adaptive output changed request difficulty")
                data.validate_exam_references(exam)
        except (ValidationError, ValueError) as exc:
            raise ApiFailure(
                500, "INVALID_EXAM_OUTPUT", "Service output không đúng contract."
            ) from exc
        request.app.state.exams.save(exam)
        return exam

    @router.get("/exams/{exam_id}", response_model=ExamResponse)
    def exam(exam_id: str, request: Request) -> ExamResponse:
        return request.app.state.exams.get(exam_id)

    @router.post("/exams/plan", response_model=ExamPlan)
    def plan(
        payload: GenerateExamRequest,
        request: Request,
        data: Annotated[StaticDataAdapter, Depends(get_data)],
    ) -> ExamPlan:
        if payload.generation_mode != "adaptive":
            raise ApiFailure(
                422, "ADAPTIVE_PLAN_REQUIRED", "Preview is for adaptive generation"
            )
        return AdaptiveExamGenerator(
            data, relationships=request.app.state.relationships
        ).plan(payload, data.get_profile(payload.student_id))

    @router.post("/exams/{exam_id}/approve", response_model=ExamResponse)
    def approve(
        exam_id: str,
        payload: ApproveExamRequest,
        request: Request,
        data: Annotated[StaticDataAdapter, Depends(get_data)],
    ) -> ExamResponse:
        store = request.app.state.exams
        current = store.get(exam_id)
        reviewed = public_exam(approve_exam(core_exam(current), payload), current)
        try:
            if current.generation_mode == "adaptive":
                core_data(data).validate_exam_references(core_exam(reviewed))
            else:
                data.validate_exam_references(reviewed)
        except (ValueError, ValidationError) as exc:
            raise ApiFailure(
                409, "EXAM_NOT_READY", "Stored source proof is no longer valid"
            ) from exc
        store.replace(reviewed, expected_revision=payload.expected_revision)
        return reviewed

    @router.post(
        "/exams/{exam_id}/questions/{question_id}/regenerate",
        response_model=ExamResponse,
    )
    def regenerate(
        exam_id: str,
        question_id: str,
        payload: RegenerateQuestionRequest,
        request: Request,
        data: Annotated[StaticDataAdapter, Depends(get_data)],
        service: Annotated[ExamGenerator, Depends(get_exam_generator)],
    ) -> ExamResponse:
        store = request.app.state.exams
        current = store.get(exam_id)
        check_revision(current, payload.expected_revision)
        require_template_regeneration(current, question_id)
        if request.app.state.generator is None:
            state = request.app.state
            service = AdaptiveExamGenerator(
                data, state.qwen_client, fake=state.backend == "fake"
            )
        if not hasattr(service, "regenerate_question"):
            raise ApiFailure(
                409,
                "REGENERATION_UNSUPPORTED",
                "Service cannot regenerate Template instances",
            )
        regenerated = ExamResponse.model_validate(
            service.regenerate_question(current.model_copy(deep=True), question_id)
        )
        if (regenerated.evidence_count, regenerated.data_status) != (
            current.evidence_count,
            current.data_status,
        ):
            raise ApiFailure(
                500, "INVALID_EXAM_OUTPUT", "Regeneration changed profile metadata"
            )
        validate_regeneration(
            core_exam(current),
            core_exam(regenerated),
            question_id,
            data=core_data(data),
        )
        core_data(data).validate_exam_references(core_exam(regenerated))
        store.replace(regenerated, expected_revision=payload.expected_revision)
        return regenerated

    api.include_router(router)
    mount_ui(api, require_teacher)
    # Registered last so CORS wraps the response/error boundary above.
    origins = [
        value.strip()
        for value in (
            os.getenv("API_CORS_ORIGINS") or os.getenv("FAKE_API_CORS_ORIGINS", "")
        ).split(",")
        if value.strip()
    ]
    if origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    return api


app = create_app()
