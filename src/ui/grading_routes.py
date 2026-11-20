"""Separate grading page; content APIs use the existing workspace authentication."""

from pathlib import Path

from fastapi.responses import FileResponse

ASSETS = Path(__file__).resolve().parent / "static"


def mount_grading_ui(app):
    @app.get("/grading", include_in_schema=False)
    def grading_page():
        return FileResponse(
            ASSETS / "grading.html",
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )
