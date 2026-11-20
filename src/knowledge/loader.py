import json
from pathlib import Path
from typing import Any


class KnowledgeLoadError(Exception):
    """Raised when a knowledge JSON file cannot be loaded."""

def load_json(path: str | Path) -> Any:
    """Load JSON data from a file.

    Args:
        path: Path to the JSON file.

    Returns:
        The parsed JSON data.

    Raises:
        KnowledgeLoadError: If the file does not exist or contains invalid JSON.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise KnowledgeLoadError(
            f"Knowledge file does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise KnowledgeLoadError(
            f"Knowledge path is not a file: {file_path}"
        )

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise KnowledgeLoadError(
            f"Invalid JSON in file {file_path}: {exc}"
        ) from exc

    except OSError as exc:
        raise KnowledgeLoadError(
            f"Cannot read file {file_path}: {exc}"
        ) from exc
