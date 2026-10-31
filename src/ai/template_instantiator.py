"""Bounded interpreter for the SQL bank's JSON parameters and formula strings.

No code execution: only integer/Fraction arithmetic, sum, C/P and factorial are
accepted. Descriptive conditional algorithms are explicitly unsupported. Sampling
uses a finite subset of unbounded authored ranges (0..12, at most four items),
which is a resource limit, never an invented mathematical condition.
"""

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from math import comb, factorial
from random import Random
from string import Formatter

from pydantic import Field, model_validator

from src.api.schemas import (
    LEVELS,
    Answer,
    CognitiveLevel,
    ContractModel,
    GradeLevel,
    Identifier,
    TemplateInstanceRecord,
    Text,
)


class UnsupportedTemplate(ValueError):
    pass


class TemplateDefinition(ContractModel):
    template_id: Identifier
    template_content: Text
    parameter_rules: dict
    answer_rule: Text
    solution_rule: Text
    difficulty: int = Field(strict=True, ge=1)
    skill_ids: list[Identifier] = Field(min_length=1)
    grade_level: GradeLevel
    topic_id: str

    @model_validator(mode="after")
    def unique_skills(self):
        if len(set(self.skill_ids)) != len(self.skill_ids) or any(
            s not in {f"A{i:03}" for i in range(1, 10)} for s in self.skill_ids
        ):
            raise ValueError(
                "Templates require unique approved A001-A009 skill mappings"
            )
        return self

    @property
    def cognitive_level(self) -> CognitiveLevel:
        return LEVELS[min(self.difficulty, 4) - 1]


def template_digest(template: TemplateDefinition) -> str:
    return hashlib.sha256(
        json.dumps(
            template.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()


@dataclass
class InstantiatedTemplate:
    template: TemplateDefinition
    record: TemplateInstanceRecord
    content: str
    answer: Answer
    solution_steps: list[str]


class TemplateInstantiator:
    max_attempts = 96
    max_integer = 12

    def _expressions(self, rule):
        if len(rule) > 512:
            raise UnsupportedTemplate("Answer expression is too long")
        parts = [p.strip() for p in rule.split("=")]
        if len(parts) < 2 or parts[0] not in ("N", "P(n)", "C(n,2)"):
            raise UnsupportedTemplate("Answer rule is not a supported explicit formula")
        expressions = parts[1:]
        if parts[0] != "N":
            expressions = [parts[0]] + expressions
        return [
            ast.parse(
                re.sub(r"(\([^()]+\)|\b[a-zA-Z_]\w*)!", r"factorial(\1)", p),
                mode="eval",
            ).body
            for p in expressions
        ]

    def _evaluate(self, node, parameters):
        if (
            isinstance(node, ast.Constant)
            and type(node.value) is int
            and 0 <= node.value <= 100
        ):
            return Fraction(node.value)
        if isinstance(node, ast.Name) and node.id in parameters:
            value = parameters[node.id]
            if type(value) is int:
                return Fraction(value)
            if isinstance(value, list) and all(type(v) is int for v in value):
                return value
        if isinstance(node, ast.BinOp) and type(node.op) in (
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
        ):
            a, b = (
                self._evaluate(node.left, parameters),
                self._evaluate(node.right, parameters),
            )
            if not isinstance(a, Fraction) or not isinstance(b, Fraction):
                raise UnsupportedTemplate("Arithmetic requires numbers")
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if b:
                return a / b
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            args = [self._evaluate(a, parameters) for a in node.args]
            if node.func.id == "sum" and len(args) == 1 and isinstance(args[0], list):
                return Fraction(sum(args[0]))
            if all(
                isinstance(a, Fraction) and a.denominator == 1 and 0 <= a <= 20
                for a in args
            ):
                values = [int(a) for a in args]
                if node.func.id in ("P", "factorial") and len(values) == 1:
                    return Fraction(factorial(values[0]))
                if node.func.id == "C" and len(values) == 2 and values[1] <= values[0]:
                    return Fraction(comb(*values))
        raise UnsupportedTemplate(
            "Unsupported operation or invalid operands in answer rule"
        )

    def _bound(self, value, parameters):
        if type(value) is int:
            return value
        if isinstance(value, str) and type(parameters.get(value)) is int:
            return parameters[value]
        raise UnsupportedTemplate("Unsupported numeric bound")

    def parameters(self, template, random):
        result = {}
        for name, rule in template.parameter_rules.items():
            if not isinstance(rule, dict) or not set(rule) <= {
                "type",
                "min",
                "max",
                "value",
                "description",
                "items",
                "min_length",
                "length",
                "length_equals",
                "unique_items",
            }:
                raise UnsupportedTemplate("Unknown parameter-rule representation")
            kind = rule.get("type")
            if kind == "integer":
                low = self._bound(rule.get("min", 0), result)
                high = min(
                    self.max_integer,
                    self._bound(rule.get("max", self.max_integer), result),
                )
                value = rule.get(
                    "value", low if random is None else random.randint(low, high)
                )
                if type(value) is not int or not 0 <= low <= value <= high:
                    raise UnsupportedTemplate("Invalid integer parameter range/value")
                result[name] = value
            elif kind == "array" and "value" not in rule:
                items = rule.get("items", {})
                if (
                    not isinstance(items, dict)
                    or items.get("type") != "integer"
                    or not set(items) <= {"type", "min", "max"}
                ):
                    raise UnsupportedTemplate(
                        "Only bounded integer-array parameters are supported"
                    )
                low = self._bound(items.get("min", 0), result)
                high = min(
                    self.max_integer,
                    self._bound(items.get("max", self.max_integer), result),
                )
                length = rule.get("length", result.get(rule.get("length_equals")))
                if length is None:
                    minimum = rule.get("min_length", 1)
                    length = (
                        minimum
                        if random is None
                        else random.randint(minimum, min(4, minimum + 2))
                    )
                if (
                    type(length) is not int
                    or not 1 <= length <= 12
                    or not 0 <= low <= high
                ):
                    raise UnsupportedTemplate("Invalid array length or bounds")
                if rule.get("unique_items"):
                    if high - low + 1 < length:
                        raise UnsupportedTemplate(
                            "Not enough distinct values in the declared range"
                        )
                    values = (
                        list(range(low, low + length))
                        if random is None
                        else random.sample(range(low, high + 1), length)
                    )
                else:
                    values = [
                        low if random is None else random.randint(low, high)
                        for _ in range(length)
                    ]
                result[name] = values
            elif kind in ("boolean", "string") and "value" in rule:
                value = rule["value"]
                if type(value) is not (bool if kind == "boolean" else str):
                    raise UnsupportedTemplate("Invalid fixed parameter type")
                result[name] = value
            elif (
                name == "groups"
                and kind in ("disjoint_groups", "object")
                and rule.get("description")
            ):
                # These stored declarations describe the structure of the groups;
                # they are not runtime placeholders or values to invent.
                continue
            else:
                raise UnsupportedTemplate(
                    "Unsupported parameter type or missing explicit value"
                )
        return result

    def _validate_parameters(self, template, parameters):
        # Validate concrete values using the original declarations, not sampled
        # examples. The same resource bounds apply to materialization/retrieval.
        expected = self.parameters(template, None)
        if set(parameters) != set(expected):
            raise UnsupportedTemplate(
                "Instance parameter names do not match the template"
            )
        for name, value in parameters.items():
            rule = template.parameter_rules[name]
            kind = rule["type"]
            if "value" in rule and value != rule["value"]:
                raise UnsupportedTemplate("Changed fixed mathematical condition")
            if kind == "integer":
                low = self._bound(rule.get("min", 0), parameters)
                high = min(
                    self.max_integer,
                    self._bound(rule.get("max", self.max_integer), parameters),
                )
                if type(value) is not int or not low <= value <= high:
                    raise UnsupportedTemplate("Integer parameter violates its rule")
            elif kind == "array":
                if not isinstance(value, list) or not 1 <= len(value) <= 12:
                    raise UnsupportedTemplate("Invalid array parameter")
                length = rule.get("length", parameters.get(rule.get("length_equals")))
                if (length is not None and len(value) != length) or len(
                    value
                ) < rule.get("min_length", 1):
                    raise UnsupportedTemplate("Array length violates its rule")
                if rule.get("unique_items") and len(value) != len(set(value)):
                    raise UnsupportedTemplate("Array parameter is not distinct")
                item = rule["items"]
                if any(
                    type(v) is not int
                    or not item.get("min", 0)
                    <= v
                    <= min(self.max_integer, item.get("max", self.max_integer))
                    for v in value
                ):
                    raise UnsupportedTemplate("Array item violates its rule")
            elif type(value) is not type(expected[name]):
                raise UnsupportedTemplate("Changed fixed parameter type")

    def materialize(
        self, template: TemplateDefinition, parameters: dict
    ) -> InstantiatedTemplate:
        self._validate_parameters(template, parameters)
        expressions = self._expressions(template.answer_rule)
        if any(sum(1 for _ in ast.walk(node)) > 64 for node in expressions):
            raise UnsupportedTemplate("Answer expression is too complex")
        answers = [self._evaluate(node, parameters) for node in expressions]
        if (
            not answers
            or not all(isinstance(a, Fraction) and a == answers[0] for a in answers)
            or answers[0].denominator != 1
            or not 0 <= answers[0] <= 10**30
        ):
            raise UnsupportedTemplate(
                "Formula branches disagree or result is not a nonnegative count"
            )
        for _, name, spec, conversion in Formatter().parse(template.template_content):
            if name is not None and (name not in parameters or spec or conversion):
                raise UnsupportedTemplate(
                    "Template placeholders must be plain declared parameters"
                )
        rendered = {
            k: ", ".join(map(str, v)) if isinstance(v, list) else str(v)
            for k, v in parameters.items()
        }
        content = template.template_content.format_map(rendered)
        digest = template_digest(template)
        mathematical_parameters = dict(parameters)
        if template.answer_rule.strip() == "N = sum(counts)" and "counts" in parameters:
            mathematical_parameters["counts"] = sorted(parameters["counts"])
        signature = hashlib.sha256(
            json.dumps(
                [template.template_id, digest, mathematical_parameters],
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        answer = str(int(answers[0]))
        substitution = "; ".join(
            f"{k}={v}"
            for k, v in parameters.items()
            if type(v) is int or isinstance(v, list)
        )
        steps = [
            template.solution_rule,
            f"Thay {substitution} vào quy tắc {template.answer_rule}. Kết quả: {answer}.",
        ]
        return InstantiatedTemplate(
            template,
            TemplateInstanceRecord(
                instance_id="TI_" + signature,
                parameters=parameters,
                signature=signature,
                template_digest=digest,
            ),
            content,
            Answer(correct_answer=answer, explanation="\n".join(steps)),
            steps,
        )

    def instances(self, template, count, *, seed=0, excluded=()):
        random = Random(str(seed) + ":" + template.template_id)
        seen, result = set(excluded), []
        # Check the rule format even when no sample can be generated.
        self._expressions(template.answer_rule)
        last_error = None
        for _ in range(self.max_attempts):
            try:
                instance = self.materialize(template, self.parameters(template, random))
            except (
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                ZeroDivisionError,
            ) as exc:
                last_error = exc
                continue
            if instance.record.signature not in seen:
                result.append(instance)
                seen.add(instance.record.signature)
                if len(result) == count:
                    break
        if not result and last_error is not None:
            raise UnsupportedTemplate(str(last_error)) from last_error
        return result
