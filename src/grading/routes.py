"""Protected API using the workspace's existing teacher bearer dependency."""

from fastapi import APIRouter, Depends, Request

from src.api.data_adapter import ApiFailure
from src.grading.schemas import JobEnvelope, JobRequest


def mount_grading(app, require_teacher):
    router = APIRouter(
        prefix="/api/v1/grading",
        tags=["grading"],
        dependencies=[Depends(require_teacher)],
    )

    @router.post("/jobs", status_code=202, response_model=JobEnvelope)
    def submit(payload: JobRequest, request: Request):
        return request.app.state.grading.submit(payload)

    @router.get("/jobs/{job_id}", response_model=JobEnvelope)
    def get_job(job_id: str, request: Request):
        return request.app.state.grading.get(job_id)

    @router.get("/jobs/{job_id}/result", response_model=JobEnvelope)
    def get_result(job_id: str, request: Request):
        envelope = request.app.state.grading.get(job_id)
        if envelope["metadata"]["state"] != "COMPLETED":
            raise ApiFailure(
                409,
                "GRADING_RESULT_NOT_COMPLETE",
                "Job chưa xử lý hết các câu; xem tiến độ và kết quả đã lưu tại GET job.",
            )
        return envelope

    app.include_router(router)
