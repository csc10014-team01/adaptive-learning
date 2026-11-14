"""Labeled extraction checks, never an LLM judge or a student grading engine."""

import itertools
import re
import unicodedata
from collections import Counter


def norm(text):
    text = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"\s+", "", text.replace("×", "*").replace("·", "*").replace("÷", "/"))


def independent_answer(case):
    """Explicit fixture dispatch; never eval/exec an authored formula."""
    p, tid = case["parameters"], case["template_id"]
    if tid == "EA0001":
        return sum(p["counts"])
    if tid == "EA0003":
        return sum(1 for _ in itertools.product(range(p["n1"]), range(p["n2"])))
    if tid == "EA0004":
        return sum(a != b for a, b in itertools.product(range(p["n"]), repeat=2))
    if tid == "EA0012":
        return sum(1 for _ in itertools.combinations(range(p["n"]), 2))
    if tid == "EA0017":
        return sum(1 for _ in itertools.permutations(range(p["n"])))
    raise ValueError(f"No independent verifier for {tid}")


def check_fixture(case):
    if independent_answer(case) != case["expected_answer"]:
        raise ValueError(f"Bad fixture answer: {case['id']}")


def numeric_facts(text):
    return Counter(re.findall(r"\d+(?:[.,]\d+)?", text))


def phraser_score(case, output):
    question = output["question"]
    issues = []
    required, actual = numeric_facts(case["source"]), numeric_facts(question)
    # Match the experimental production convention: repeating an existing fact
    # in a story is allowed, introducing a new value or omitting one is not.
    if set(actual) != set(required) or any(actual[n] < count for n, count in required.items()):
        issues.append("changed_numeric_facts")
    # Authored lexical guards are deliberately conservative. Paraphrases need review.
    for family in case["guards"]:
        if not any(re.search(pattern, question, re.I) for pattern in family):
            issues.append("missing_constraint_guard:" + "|".join(family))
    if re.search(r"```|<think>|(?:đáp án|lời giải|kết quả là)\s*[:=]?|\d\s*[=!]", question, re.I):
        issues.append("explanation_or_answer_leak")
    if case["mode"] == "indirect" and re.search(r"bao nhiêu cách (?:chọn|sắp xếp)", question, re.I):
        issues.append("indirect_asks_direct_operation")
    definite = [x for x in issues if not x.startswith("missing_constraint_guard:")]
    return {"status": "incorrect_result" if definite else "needs_review",
            "violations": issues, "numeric_ok": "changed_numeric_facts" not in issues,
            "math_correct": None, "answer_preservation": "requires_manual_review",
            "model_review": None, "requires_review": True,
            "manual_checks": ["natural Vietnamese", "full constraint preservation",
                              "no invented assumptions", "same counted set and answer",
                              "direct/indirect cognitive intent"]}


def parser_score(case, output):
    expected = {e["line"]: e for e in case["expected_steps"]}
    actual = {}
    issues = []
    for step in output["steps"]:
        line = step["line"]
        if line in actual:
            issues.append(f"duplicate_line:{line}")
        actual[line] = step
    correct = Counter()
    missed_uncertainty = 0
    for line, label in expected.items():
        step = actual.get(line)
        if step is None:
            issues.append(f"missing_line:{line}")
            if set(label["required_flags"]) & {"ambiguous", "incomplete"}:
                missed_uncertainty += 1
            continue
        checks = {
            "expression": norm(step["expression"]) in {norm(x) for x in label["expressions"]},
            "purpose": step["purpose"] in label["purposes"],
            "reference": step["reference"] in label["references"],
            "flags": set(label["required_flags"]) <= set(step["flags"]) <= set(label["allowed_flags"]),
        }
        for key, ok in checks.items():
            correct[key] += int(ok)
            if not ok:
                issues.append(f"{key}:{line}")
        correct["all"] += int(all(checks.values()))
        required_uncertainty = set(label["required_flags"]) & {"ambiguous", "incomplete"}
        if required_uncertainty - set(step["flags"]):
            missed_uncertainty += 1
    extra = set(actual) - set(expected)
    if extra:
        issues.append("invented_or_nonmathematical_lines:" + str(sorted(extra)))
    if case["review_required"] and not output["review"]:
        issues.append("missing_teacher_review")
        missed_uncertainty += 1
    # A proxy only: unflagged known-invalid reasoning without a model review request.
    # A missing line is an extraction error, not evidence of an acceptance decision.
    invalid_lines = [e["line"] for e in expected.values()
                     if set(e["required_flags"]) & {"arithmetic", "formula", "constraint"}]
    false_accept = bool(invalid_lines) and not output["review"] and any(
        line in actual and not set(actual[line]["flags"]) & {"arithmetic", "formula", "constraint", "ambiguous"}
        for line in invalid_lines)
    alternative_ok = None
    if case["alternative"]:
        alternative_ok = not issues and not any(
            set(s["flags"]) & {"arithmetic", "formula", "constraint"} for s in output["steps"])
    return {"status": "incorrect_result" if issues else ("needs_review" if output["review"] else "pass_labeled"),
            "violations": issues, "expected_step_count": len(expected),
            "extracted_step_count": len(output["steps"]),
            "covered_step_count": len(set(actual) & set(expected)),
            "correct_steps": correct["all"],
            "correct_expressions": correct["expression"], "correct_purposes": correct["purpose"],
            "correct_references": correct["reference"], "correct_flags": correct["flags"],
            "labeled_ok": not issues, "alternative_ok": alternative_ok,
            "false_acceptance_proxy": false_accept, "missed_uncertainty": missed_uncertainty,
            "model_review": output["review"], "requires_review": bool(issues) or output["review"],
            "math_correct": None}


def score(case, output):
    return phraser_score(case, output) if case["category"] == "phraser" else parser_score(case, output)
