"""Bounded fact checks; not a proof of mathematical or semantic equivalence."""

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from math import comb, factorial, perm

from src.ai.problem_spec import ProblemSpec


def numbers(text: str) -> Counter:
    return Counter(
        re.findall(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?|(?<=\w)\d+(?:[.,]\d+)?", text)
    )


def numeric_facts_preserved(source: str, candidate: str) -> bool:
    return numbers(source) == numbers(candidate)


def experimental_wording_checks(source: str, candidate: str) -> None:
    """Basic blocking checks only; no proof of meaning or cognitive equivalence."""
    if not isinstance(candidate, str) or not 20 <= len(candidate.strip()) <= 16000:
        raise ValueError("Invalid experimental question text")
    if "{" in candidate or "}" in candidate:
        raise ValueError("Unresolved experimental placeholders")
    if re.search(
        r"day/session/page|\b(?:mandatory_semantics|context_suggestion|previous_wording_to_avoid)\b",
        candidate,
        re.IGNORECASE,
    ):
        raise ValueError(
            "Experimental output contains prompt scaffolding rather than natural question wording"
        )
    required, actual = numbers(source), numbers(candidate)
    # Repeating an existing fact in a story is allowed; inventing a numeric value
    # or omitting an original occurrence is not. Number words remain a limitation.
    if set(actual) != set(required) or any(
        actual[n] < count for n, count in required.items()
    ):
        raise ValueError("Changed or missing numeric facts")
    before, after = constraint_signatures(source), constraint_signatures(candidate)
    for family in before:
        expected, observed = set(before[family]), set(after[family])
        if expected and observed and not observed <= expected:
            raise ValueError(
                "Detectable contradictory mathematical constraint: " + family
            )
    if normalize_statement(source) in normalize_statement(candidate) or near_duplicate(
        source, candidate
    ):
        raise ValueError(
            "Indirect copied the Direct statement rather than contextualizing it"
        )
    if re.search(
        r"(?:hỏi\s+)?có\s+bao nhiêu cách\s+(?:sắp xếp|chọn|xếp|lập)",
        candidate,
        re.IGNORECASE,
    ):
        raise ValueError(
            "Indirect still asks the Direct counting operation; ask a contextual outcome instead"
        )
    if re.search(
        r"(?:\b\d+\s*!|\b[CAP]\s*\(\s*\d|công thức|quy tắc (?:cộng|nhân))",
        candidate,
        re.IGNORECASE,
    ):
        raise ValueError(
            "Indirect states the counting formula/technique instead of a contextual question"
        )


def normalize_statement(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def verified_count(spec: ProblemSpec) -> int:
    """Independent deterministic check, not part of expression planning."""
    n, k = spec.parameters.n, spec.parameters.k
    if spec.mathematical_structure == "permutation":
        return factorial(n)
    if spec.mathematical_structure == "combination":
        return comb(n, k)
    return n**k if spec.constraints.replacement_allowed else perm(n, k)


def constraint_signatures(text: str) -> dict[str, Counter]:
    """Small explicit vocabulary; unknown prose is never certified by this check."""
    text = normalize_statement(text)
    patterns = {
        "order": [
            ("no", r"không (?:có )?xét (?:đến )?thứ tự"),
            ("yes", r"(?:có )?xét (?:đến )?thứ tự"),
        ],
        "replacement": [
            ("no", r"không (?:được )?(?:hoàn lại|lặp lại)"),
            ("yes", r"(?:có|được|cho phép) (?:hoàn lại|lặp lại)"),
        ],
        "distinct": [
            ("no", r"không phân biệt|giống nhau"),
            ("yes", r"phân biệt|khác nhau"),
        ],
        "bound": [
            ("minimum", r"ít nhất"),
            ("maximum", r"nhiều nhất"),
            ("exact", r"đúng (?:một|hai|ba|\d+)"),
        ],
        "parity": [("even", r"số chẵn"), ("odd", r"số lẻ")],
    }
    result = {}
    for family, entries in patterns.items():
        remaining = text
        result[family] = Counter()
        for value, pattern in entries:
            matches = list(re.finditer(pattern, remaining))
            if matches:
                result[family][value] += len(matches)
                remaining = re.sub(pattern, " ", remaining)
    return result


def changed_constraints(source: str, candidate: str, *, structured: bool) -> bool:
    before, after = constraint_signatures(source), constraint_signatures(candidate)
    # For legacy prose, only an explicit contradictory marker is a definite
    # failure. Omission/paraphrase remains unresolved. Structured inputs use
    # authored guards and reject additions/removals in this known vocabulary.
    return any(
        before[k] != after[k] and (structured or (before[k] and after[k]))
        for k in before
    )


def near_duplicate(left: str, right: str) -> bool:
    left, right = normalize_statement(left), normalize_statement(right)
    if left == right:
        return True
    # A different numerical problem is not a wording duplicate.
    return (
        numbers(left) == numbers(right)
        and SequenceMatcher(None, left, right).ratio() >= 0.96
    )
