"""Buildless, same-origin teacher UI; all data still passes through protected APIs."""

from pathlib import Path

from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ASSETS = Path(__file__).resolve().parent / "static"


def mount_ui(app, require_teacher):
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(
            ASSETS / "index.html",
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get(
        "/ui/config", dependencies=[Depends(require_teacher)], include_in_schema=False
    )
    def config():
        return {
            "backend": app.state.backend,
            "profile_source": app.state.profile_source,
            "model": app.state.qwen_client.model
            if app.state.backend == "qwen"
            else None,
            "generation_timeout_seconds": app.state.qwen_client.exam_timeout,
        }

    app.mount("/ui/assets", StaticFiles(directory=ASSETS), name="teacher-ui-assets")
