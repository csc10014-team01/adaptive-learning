"""The new teacher workspace uses the team's protected API boundary."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


def test_teacher_ui_is_served_and_exposes_public_contract_names():
    with TestClient(create_app(teacher_token="route-test")) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "frame-ancestors 'none'" in index.headers["content-security-policy"]
        assert index.headers["cache-control"] == "no-store"
        javascript = client.get("/ui/assets/app.js")
        assert javascript.status_code == 200
        assert "profile.student_name" in javascript.text
        assert "template_presentation" in javascript.text
        config = client.get(
            "/ui/config", headers={"Authorization": "Bearer route-test"}
        )
        assert config.status_code == 200
        assert config.json()["backend"] == "fake"
        assert config.json()["profile_source"] == "json"
        assert "route-test" not in index.text + javascript.text + config.text


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/exams/plan"),
        ("post", "/api/v1/exams/UNKNOWN/approve"),
        ("post", "/api/v1/exams/UNKNOWN/questions/UNKNOWN/regenerate"),
        ("get", "/ui/config"),
    ],
)
def test_new_routes_require_the_existing_teacher_authentication(method, path):
    with TestClient(create_app(teacher_token="route-test")) as client:
        response = getattr(client, method)(path)
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "TEACHER_AUTH_REQUIRED"
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.headers["cache-control"] == "no-store"
