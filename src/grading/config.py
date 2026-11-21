"""Validated grading-only configuration; never changes generation settings."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]


class GradingConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, validate_default=True
    )
    model: str = Field(default="qwen3:4b-q4_K_M", min_length=1, max_length=128)
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = Field(default=120, gt=0, le=600)
    num_predict: int = Field(default=1200, ge=160, le=8192)
    num_ctx: int = Field(default=8192, ge=1024, le=32768)
    max_repairs: int = Field(default=1, ge=0, le=1)
    capacity: int = Field(default=4, ge=1, le=32)
    db_path: Path = ROOT / "data/runtime/grading.db"
    debug_enabled: bool = False
    debug_dir: Path = ROOT / "data/runtime/grading_debug"

    @field_validator("model")
    @classmethod
    def valid_model(cls, value):
        if value != value.strip() or any(c.isspace() for c in value):
            raise ValueError("GRADING_MODEL must be an explicit model tag")
        return value

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        url = urlsplit(value)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError(
                "OLLAMA_BASE_URL must be an HTTP origin without credentials"
            )
        return value.rstrip("/")

    @field_validator("db_path", "debug_dir")
    @classmethod
    def runtime_path(cls, value):
        value = (value if value.is_absolute() else ROOT / value).resolve()
        if value.is_relative_to(ROOT) and not any(
            value.is_relative_to(root)
            for root in (
                ROOT / "data/runtime",
                ROOT / ".pytest_tmp_mira",
            )
        ):
            raise ValueError(
                "Inside this repository, grading storage must use data/runtime (or isolated pytest scratch)"
            )
        return value

    @classmethod
    def from_env(cls):
        fields = {
            "model": "GRADING_MODEL",
            "base_url": "OLLAMA_BASE_URL",
            "timeout_seconds": "GRADING_TIMEOUT_SECONDS",
            "num_predict": "GRADING_NUM_PREDICT",
            "num_ctx": "GRADING_NUM_CTX",
            "max_repairs": "GRADING_MAX_REPAIRS",
            "capacity": "GRADING_QUEUE_CAPACITY",
            "db_path": "GRADING_DB",
            "debug_enabled": "GRADING_DEBUG",
            "debug_dir": "GRADING_DEBUG_DIR",
        }
        return cls(**{f: os.environ[e] for f, e in fields.items() if e in os.environ})
