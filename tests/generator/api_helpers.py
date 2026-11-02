from src.api.main import create_app
from tests.generator.doubles import EchoTemplateClient

HEADERS = {"Authorization": "Bearer hybrid-test"}


def application(tmp_path, data, client=None):
    model = client or EchoTemplateClient()
    app = create_app(
        backend="qwen",
        profile_source="m3",
        teacher_token="hybrid-test",
        qwen_client=model,
        exam_db=tmp_path / "drafts.db",
        instance_seed=42,
    )
    app.state.data = data
    return app, model
