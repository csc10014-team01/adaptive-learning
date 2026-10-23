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
    ApiError, ApiErrorResponse, ErrorDetail, ExamResponse, GenerateExamRequest,
    StudentListResponse, StudentProfileResponse, TopicListResponse,
)
from src.api.services import ExamGenerator, FakeExamGenerator, InMemoryExamStore, question_slots

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def require_teacher(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    configured = request.app.state.teacher_token
    if not configured:
        raise ApiFailure(503, "TEACHER_ACCESS_NOT_CONFIGURED", "Cần cấu hình FAKE_API_TEACHER_TOKEN.")
    if credentials is None:
        raise ApiFailure(401, "TEACHER_AUTH_REQUIRED", "Cần teacher bearer token.")
    if not secrets.compare_digest(credentials.credentials.encode(), configured.encode()):
        raise ApiFailure(403, "TEACHER_ACCESS_DENIED", "Không có quyền truy cập teacher API.")


def get_data(request: Request) -> StaticDataAdapter:
    with request.app.state.data_lock:
        if request.app.state.data is None:
            request.app.state.data = StaticDataAdapter(
                request.app.state.fixture_dir, request.app.state.bank_path,
            )
        return request.app.state.data


def get_exam_generator(
    request: Request, data: Annotated[StaticDataAdapter, Depends(get_data)],
) -> ExamGenerator:
    return request.app.state.generator or FakeExamGenerator(data)


def error_response(status: int, code: str, message: str, details: list[ErrorDetail] | None = None) -> JSONResponse:
    payload = ApiErrorResponse(error=ApiError(code=code, message=message, details=details or []))
    return JSONResponse(
        status_code=status, content=payload.model_dump(mode="json"),
        headers={"Cache-Control": "no-store", **({"WWW-Authenticate": "Bearer"} if status == 401 else {})},
    )


def create_app(
    *, fixture_dir: Path | None = None, bank_path: Path = DEFAULT_BANK,
    teacher_token: str | None = None, generator: ExamGenerator | None = None,
) -> FastAPI:
    api = FastAPI(title="Smart Exam Generator — Fake MVP1", version="1.0.0")
    api.state.teacher_token = teacher_token if teacher_token is not None else os.getenv("FAKE_API_TEACHER_TOKEN")
    api.state.fixture_dir = fixture_dir or Path(os.getenv("FAKE_API_FIXTURE_DIR", str(DEFAULT_FIXTURES)))
    api.state.bank_path = bank_path
    api.state.data = None
    api.state.data_lock = Lock()
    api.state.generator = generator
    api.state.exams = InMemoryExamStore()

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
        logger.exception("Unexpected fake API failure at %s", request.url.path)
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
        payload: GenerateExamRequest, request: Request,
        data: Annotated[StaticDataAdapter, Depends(get_data)],
        service: Annotated[ExamGenerator, Depends(get_exam_generator)],
    ) -> ExamResponse:
        student = data.get_profile(payload.student_id)
        if payload.generation_mode == "adaptive" and student.evidence_count < 3:
            raise ApiFailure(409, "ADAPTIVE_NOT_ALLOWED", "Adaptive yêu cầu evidence_count >= 3.")
        try:
            # The generator receives isolated working copies. Validate against the
            # trusted originals, including nested lists/models, after it returns.
            exam = ExamResponse.model_validate(service.generate(
                payload.model_copy(deep=True), student.model_copy(deep=True),
            ))
            expected = (
                exam.student_id == student.student_id,
                exam.grade_level == student.grade_level,
                exam.evidence_count == student.evidence_count,
                exam.data_status == student.data_status,
                exam.generation_mode == payload.generation_mode,
                exam.total_questions == payload.total_questions,
                exam.duration_minutes == payload.duration_minutes,
                exam.topic_id == payload.selected_topic_ids[0],
                {level: sum(q.cognitive_level == level for q in exam.questions)
                 for level in question_slots(payload)} == question_slots(payload),
            )
            if not all(expected):
                raise ValueError("Service output does not match request/profile")
            data.validate_exam_references(exam)
        except (ValidationError, ValueError) as exc:
            raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Service output không đúng contract.") from exc
        request.app.state.exams.save(exam)
        return exam

    @router.get("/exams/{exam_id}", response_model=ExamResponse)
    def exam(exam_id: str, request: Request) -> ExamResponse:
        return request.app.state.exams.get(exam_id)

    api.include_router(router)
    # Registered last so CORS wraps the response/error boundary above.
    origins = [value.strip() for value in os.getenv("FAKE_API_CORS_ORIGINS", "").split(",") if value.strip()]
    if origins:
        api.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    return api


app = create_app()
