"""Template presentation provenance, independent of mathematical allocation.

Verified patterns are a finite wording allowlist, not a semantic-equivalence
engine. Experimental capability uses basic checks and never claims author approval.
"""

import hashlib
import json
from pathlib import Path
from string import Formatter
from typing import Literal

from pydantic import Field, model_validator

from src.ai.template_instantiator import TemplateDefinition, template_digest
from src.api.schemas import CognitiveLevel, ContractModel, Identifier, TemplatePresentationRecord, Text

DEFAULT_PRESENTATIONS = Path(__file__).resolve().parents[2] / "config/template_presentations.json"
SOURCE_DIRECT_ID = "sql_direct"
SOURCE_DIRECT_VERSION = "sql-direct-v1"
EXPERIMENTAL_ID = "experimental_indirect"
EXPERIMENTAL_VERSION = "experimental-indirect-v1"
EXPERIMENTAL_NOTICE = "Diễn đạt Indirect thử nghiệm — chưa kiểm chứng đầy đủ về ngữ nghĩa toán học."
EXPERIMENTAL_CONTEXTS = {
    "school": "School activities: use a different COMPLETE configuration each day, without repeats; ask the maximum number of days.",
    "club": "Club activities: each session uses a different COMPLETE configuration; ask how many sessions before a repeat.",
    "display": "Book/product exhibition: show a different COMPLETE configuration on each catalogue page; ask the number of pages.",
    "event": "Event planning: record each different COMPLETE plan once in a photo album; ask the number of photos.",
    "everyday": "Everyday experiences: a different COMPLETE option on each visit; ask the number of visits before a repeat.",
}


def is_experimental(record):
    return record is not None and record.presentation_id == EXPERIMENTAL_ID


def same_record(actual, expected):
    # Old verified/source-Direct drafts predate verification_status. Experimental
    # records never get this compatibility allowance.
    if actual.verification_status is None and not is_experimental(actual):
        actual = actual.model_copy(update={"verification_status": expected.verification_status})
    return actual == expected


class TemplatePresentation(ContractModel):
    template_id: Identifier
    presentation_id: Identifier
    generate_type: Literal["direct", "indirect"]
    pattern: Text
    required_placeholders: list[Identifier]
    permitted_context: Text
    mathematical_invariants: list[Text] = Field(min_length=1)
    required_result: Text
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    cognitive_level: CognitiveLevel
    verification_status: Literal["proposed", "verified"] = "proposed"
    verification_reference: Text | None = None
    cognitive_level_preserved: bool = Field(default=False, strict=True)
    cognitive_review_reference: Text | None = None

    @model_validator(mode="after")
    def authored_contract(self):
        fields = []
        for _, name, spec, conversion in Formatter().parse(self.pattern):
            if name is not None:
                if not name.isidentifier() or spec or conversion:
                    raise ValueError("Presentation placeholders must be plain declared names")
                fields.append(name)
        if (set(fields) != set(self.required_placeholders)
                or len(set(self.required_placeholders)) != len(self.required_placeholders)
                or self.presentation_id in (SOURCE_DIRECT_ID, EXPERIMENTAL_ID)):
            raise ValueError("Presentation placeholders/identity are inconsistent")
        if self.verification_status == "verified" and not (
            self.verification_reference and self.cognitive_level_preserved and self.cognitive_review_reference
        ):
            raise ValueError("Verified presentations need mathematical and cognitive author-review references")
        return self

    def compatible(self, template: TemplateDefinition) -> bool:
        source_fields = {name for _, name, _, _ in Formatter().parse(template.template_content) if name}
        return (self.verification_status == "verified" and self.template_id == template.template_id
                and self.source_digest == template_digest(template)
                and self.cognitive_level == template.cognitive_level
                and source_fields <= set(self.required_placeholders)
                and set(self.required_placeholders) <= set(template.parameter_rules))

    def render(self, parameters: dict) -> str:
        values = {k: ", ".join(map(str, v)) if isinstance(v, list) else str(v) for k, v in parameters.items()}
        return self.pattern.format_map(values)


class TemplatePresentations(ContractModel):
    version: Identifier
    presentations: list[TemplatePresentation] = Field(default_factory=list)
    experimental_indirect: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def unique_ids(self):
        keys = [(p.template_id, p.presentation_id) for p in self.presentations]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate Template presentation IDs")
        return self

    @classmethod
    def load(cls, path: Path = DEFAULT_PRESENTATIONS):
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def record(self, template, presentation=None):
        if presentation is None:
            version, pid, kind = SOURCE_DIRECT_VERSION, SOURCE_DIRECT_ID, "direct"
            payload = [version, template_digest(template)]
        else:
            if not presentation.compatible(template):
                raise ValueError("Presentation is unverified or incompatible with its SQL Template")
            version, pid, kind = self.version, presentation.presentation_id, presentation.generate_type
            payload = [version, presentation.model_dump(mode="json")]
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return TemplatePresentationRecord(presentation_id=pid, generate_type=kind,
            config_version=version, fingerprint=fingerprint,
            verification_status="source_direct" if presentation is None else "verified")

    def experimental_record(self, template, context_id="school"):
        if not self.experimental_indirect or template.difficulty not in (1, 2) or context_id not in EXPERIMENTAL_CONTEXTS:
            raise ValueError("Experimental Indirect is disabled or incompatible")
        payload = [EXPERIMENTAL_VERSION, template_digest(template), context_id, EXPERIMENTAL_CONTEXTS[context_id]]
        fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
        return TemplatePresentationRecord(presentation_id=EXPERIMENTAL_ID, generate_type="indirect",
            config_version=EXPERIMENTAL_VERSION, fingerprint=fingerprint,
            verification_status="experimental", context_id=context_id)

    def options(self, template):
        options = [self.record(template), *[self.record(template, p) for p in self.presentations if p.compatible(template)]]
        # Authored Indirect remains preferred when present. The experimental
        # pathway needs NO approved configuration entry.
        if self.experimental_indirect and template.difficulty in (1, 2) and not any(p.generate_type == "indirect" for p in options):
            options.append(self.experimental_record(template))
        return options

    def resolve(self, template, record, generate_type):
        """Resolve against current trusted configuration; never trust a draft's label."""
        if record is None:
            if generate_type != "direct":
                raise ValueError("Indirect Template lacks presentation provenance")
            return None  # Backward-compatible SQL Direct drafts.
        if record.generate_type != generate_type:
            raise ValueError("Presentation type differs from the question label")
        if is_experimental(record):
            if not same_record(record, self.experimental_record(template, record.context_id)):
                raise ValueError("Experimental presentation provenance changed")
            return None  # No author pattern, and never treated as verified.
        if record.presentation_id == SOURCE_DIRECT_ID:
            if not same_record(record, self.record(template)):
                raise ValueError("SQL Direct presentation fingerprint changed")
            return None
        for presentation in self.presentations:
            if (presentation.template_id == template.template_id
                    and presentation.presentation_id == record.presentation_id
                    and presentation.compatible(template) and same_record(record, self.record(template, presentation))):
                return presentation
        raise ValueError("Presentation is missing, unverified, changed or incompatible")


def validate_template_wording(instance, text, generate_type, record, registry):
    """Verified patterns stay exact; experimental wording has explicit weaker checks."""
    from src.validation.math_validator import changed_constraints, normalize_statement, numeric_facts_preserved
    presentation = registry.resolve(instance.template, record, generate_type)
    if is_experimental(record):
        from src.validation.math_validator import experimental_wording_checks
        experimental_wording_checks(instance.content, text)
        if instance.record.parameters.get("arrange_all") is True:
            import re
            # Detect an explicit all-to-one change; do not turn this experimental
            # branch into a required-phrase allowlist. Implicit/omitted conditions
            # remain an acknowledged semantic uncertainty.
            if instance.record.parameters.get("n", 0) > 1 and re.search(
                r"mỗi (?:buổi|ngày|lượt)[^.?!]{0,80}(?:dùng|sử dụng|chọn) (?:một|1) (?:phần tử|đối tượng|quyển sách|sản phẩm)",
                text, re.IGNORECASE,
            ):
                raise ValueError("Detectable change from arranging all objects to selecting one per event")
        return instance.content  # Mathematical authority; wording is experimental.
    expected = presentation.render(instance.record.parameters) if presentation else instance.content
    if not numeric_facts_preserved(instance.content, expected):
        raise ValueError("Presentation pattern changed the source numerical facts")
    if "{" in text or "}" in text:
        raise ValueError("Unresolved presentation placeholders")
    if not numeric_facts_preserved(expected, text):
        raise ValueError("Changed numeric facts")
    if changed_constraints(expected, text, structured=True):
        raise ValueError("Changed known mathematical constraints")
    if normalize_statement(expected) != normalize_statement(text):
        raise ValueError("Wording is outside the approved presentation; semantic equivalence is uncertain")
    return expected
