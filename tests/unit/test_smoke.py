from pathlib import Path


def test_repository_structure_exists():
    """Smoke test xác nhận các thư mục cốt lõi của dự án đã tồn tại."""
    root = Path(__file__).resolve().parents[2]
    assert (root / "src").is_dir()
    assert (root / "data").is_dir()
    assert (root / "docs").is_dir()
    assert (root / "eval").is_dir()
