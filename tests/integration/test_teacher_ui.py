"""Same-origin UI serving and API boundaries; no model download is required."""

from fastapi.testclient import TestClient

from src.api.main import create_app


TOKEN = "ui-integration-test-only"
HEADERS = {"Authorization": "Bearer " + TOKEN}


def test_ui_assets_are_public_but_do_not_embed_credentials_or_profiles():
    with TestClient(create_app(backend="fake", teacher_token=TOKEN)) as client:
        page = client.get("/")
        assert page.status_code == 200 and "text/html" in page.headers["content-type"]
        assert "Math Studio" in page.text and TOKEN not in page.text
        for control in ("mode", "lock-levels", "recognition", "understanding", "application", "advanced_application"):
            assert f'id="{control}"' not in page.text
        assert "độ khó được xác định tự động" in page.text
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        assert page.headers["cache-control"] == "no-store"
        for asset in ["app.js", "style.css"]:
            result = client.get("/ui/assets/" + asset)
            assert result.status_code == 200 and TOKEN not in result.text
        assert client.get("/ui/assets/does-not-exist.js").status_code == 404


def test_ui_config_requires_teacher_access_and_exposes_no_secrets():
    with TestClient(create_app(backend="fake", teacher_token=TOKEN)) as client:
        assert client.get("/ui/config").status_code == 401
        assert client.get("/ui/config", headers={"Authorization": "Bearer wrong"}).status_code == 403
        response = client.get("/ui/config", headers=HEADERS)
        assert response.status_code == 200
        assert response.json() == {"backend": "fake", "profile_source": "json", "model": None,
                                   "generation_timeout_seconds": 180}
        assert TOKEN not in response.text
        # UI routes do not alter the published business API inventory.
        assert len(client.get("/openapi.json").json()["paths"]) == 8


def test_local_demo_can_select_real_sample_profiles_plan_and_generate():
    app = create_app(backend="fake", profile_source="m3", teacher_token=TOKEN)
    with TestClient(app, headers=HEADERS) as client:
        students = client.get("/api/v1/students").json()["items"]
        assert len(students) == 20
        student = students[0]
        assert client.get(f"/api/v1/students/{student['student_id']}/profile").status_code == 200
        payload = {"student_id": student["student_id"], "selected_topic_ids": ["combinatorics"],
                   "generation_mode": "adaptive", "total_questions": 4, "duration_minutes": 45,
                   "difficulty_distribution": None}
        assert client.post("/api/v1/exams/plan", json=payload).status_code == 200
        response = client.post("/api/v1/exams/generate", json=payload)
        assert response.status_code == 200
        exam = response.json()
        assert len(exam["questions"]) == 4 and exam["provenance"]["generator"] == "fake"
        assert client.get(f"/api/v1/exams/{exam['exam_id']}").json() == exam
