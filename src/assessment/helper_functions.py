import sqlite3
from pathlib import Path
import json
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data"/"sample"/"dataset"/ "question_bank.db"

# =========================
# HELPER FUNCTIONS
# =========================

def check_required_fields(data: dict, required_fields: list) -> bool:
    """Kiểm tra các trường bắt buộc có tồn tại và không bị None."""
    if not isinstance(data, dict):
        return False

    for field in required_fields:
        if field not in data or data[field] is None:
            return False

    return True


def check_duplicate(DB_PATH, table: str, id_column: str, id_value) -> bool:
    """Kiểm tra ID đã tồn tại trong database chưa."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                f"SELECT 1 FROM {table} WHERE {id_column} = ? LIMIT 1",
                (id_value,)
            )

            return cursor.fetchone() is not None

    except sqlite3.Error as e:
        raise RuntimeError(f"Database error: {e}")


def serialize_json(data):
    """Chuyển dữ liệu có cấu trúc thành JSON string."""
    if isinstance(data, (dict, list)):
        return json.dumps(data, ensure_ascii=False)
    return data
