"""Content fingerprint prevents regenerating against a silently changed source."""

import hashlib
import json

from src.api.data_adapter import FixtureQuestion


def source_digest(source: FixtureQuestion) -> str:
    value = source.model_dump(mode="json")
    # Keep fingerprints of pre-ProblemSpec legacy drafts stable.
    if source.problem_spec is None:
        value.pop("problem_spec")
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
