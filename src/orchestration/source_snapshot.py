"""Content fingerprint prevents regenerating against a silently changed source."""

import hashlib
import json

from src.api.data_adapter import FixtureQuestion


def source_digest(source: FixtureQuestion) -> str:
    canonical = json.dumps(source.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
