
from math import isfinite
from typing import Any

"""
Validation rules for knowledge data.
Data validation rules:
- Required fields must be present.
- String fields must not be empty or contain only whitespace.
- Numeric fields must have valid numeric types and satisfy their constraints.
- Boolean values must not be accepted as numbers.
- mastery_score must be a finite number between 0 and 4.
- Lists and nested objects must follow the expected data structure.
- Invalid data raises KnowledgeValidationError.
"""


class KnowledgeValidationError(Exception):
    """Raised when knowledge data is invalid."""


def _require_fields(
    data: dict[str, Any],
    required_fields: set[str],
) -> None:
    """Check whether all required fields exist."""
    missing_fields = required_fields - data.keys()

    if missing_fields:
        raise KnowledgeValidationError(
            f"Missing required fields: {sorted(missing_fields)}"
        )


def _require_type(
    value: Any,
    expected_type: type | tuple[type, ...],
    field_name: str,
) -> None:
    """Check whether a value has the expected type."""
    if not isinstance(value, expected_type):
        raise KnowledgeValidationError(
            f"{field_name} has an invalid type"
        )


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> None:
    """Check whether a value is a non-empty string."""
    _require_type(value, str, field_name)

    if not value.strip():
        raise KnowledgeValidationError(
            f"{field_name} cannot be empty"
        )

def validate_question(data: dict[str, Any]) -> None:
    """Validate a question record."""

    required_fields = {
        "question_id",
        "grade_level",
        "skill_ids",
        "cognitive_level",
        "generate_type",
        "content",
        "answer",
    }

    _require_fields(data, required_fields)

    # Validate basic fields
    for field in ("question_id", "generate_type", "content"):
        _require_non_empty_string(data[field], field)

    # Validate grade_level
    grade_level = data["grade_level"]
    _require_type(grade_level, int, "grade_level")

    if isinstance(grade_level, bool):
        raise KnowledgeValidationError(
            "grade_level must be an integer"
        )

    if grade_level <= 0:
        raise KnowledgeValidationError(
            "grade_level must be positive"
        )

    # Validate skill_ids
    skill_ids = data["skill_ids"]
    _require_type(skill_ids, list, "skill_ids")

    if not skill_ids:
        raise KnowledgeValidationError(
            "skill_ids cannot be empty"
        )

    for skill_id in skill_ids:
        _require_non_empty_string(skill_id, "skill_id")

    # Validate cognitive_level (REAL)
    cognitive_level = data["cognitive_level"]

    _require_type(
        cognitive_level,
        (int, float),
        "cognitive_level",
    )

    if isinstance(cognitive_level, bool) or not isfinite(cognitive_level):
        raise KnowledgeValidationError(
            "cognitive_level must be a finite number"
        )

    # Validate answer
    answer = data["answer"]
    _require_type(answer, dict, "answer")

    _require_fields(
        answer,
        {"correct_answer", "explanation"},
    )

    for field in ("correct_answer", "explanation"):
        _require_non_empty_string(answer[field], field)

def validate_skill_mastery(data: dict[str, Any]) -> None:
    """Validate a skill mastery record."""

    _require_fields(
        data,
        {"skill_id", "mastery_score"},
    )

    _require_non_empty_string(data["skill_id"], "skill_id")

    mastery_score = data["mastery_score"]

    _require_type(
        mastery_score,
        (int, float),
        "mastery_score",
    )

    if (
        isinstance(mastery_score, bool)
        or not isfinite(mastery_score)
        or not 0 <= mastery_score <= 4
    ):
        raise KnowledgeValidationError(
            "mastery_score must be a finite number between 0 and 4"
        )


def validate_student(data: dict[str, Any]) -> None:
    """Validate a student profile."""

    required_fields = {
        "student_id",
        "name",
        "grade_level",
        "evidence_count",
        "skill_mastery",
        "learning_history",
    }

    _require_fields(data, required_fields)

    # Validate basic fields
    for field in ("student_id", "name"):
        _require_non_empty_string(data[field], field)

    # Validate grade_level
    grade_level = data["grade_level"]

    _require_type(grade_level, int, "grade_level")

    if isinstance(grade_level, bool) or grade_level <= 0:
        raise KnowledgeValidationError(
            "grade_level must be a positive integer"
        )

    # Validate evidence_count
    evidence_count = data["evidence_count"]

    _require_type(evidence_count, int, "evidence_count")

    if isinstance(evidence_count, bool) or evidence_count < 0:
        raise KnowledgeValidationError(
            "evidence_count must be a non-negative integer"
        )

    # Validate skill_mastery
    skill_mastery = data["skill_mastery"]

    _require_type(skill_mastery, list, "skill_mastery")

    for mastery in skill_mastery:
        _require_type(mastery, dict, "skill_mastery item")
        validate_skill_mastery(mastery)

    # Validate learning_history
    learning_history = data["learning_history"]

    _require_type(learning_history, list, "learning_history")

    for record in learning_history:
        _require_type(record, dict, "learning_history item")

        _require_fields(
            record,
            {"test_id", "wrongs"},
        )

        _require_non_empty_string(
            record["test_id"],
            "test_id",
        )

        wrongs = record["wrongs"]

        _require_type(wrongs, list, "wrongs")

        for question_id in wrongs:
            _require_non_empty_string(
                question_id,
                "question_id",
            )
