"""Allocate, resolve immutable questions/templates, generate template wording only."""

import time
import secrets
from uuid import uuid4

from src.adaptation.planner import RuleBasedPlanner
from src.ai.contracts import ValidatedQuestion, ValidationResult
from src.ai.expression_planner import ExpressionPlanner
from src.ai.template_instantiator import TemplateInstantiator, template_digest
from src.ai.template_presentations import TemplatePresentations
from src.api.data_adapter import ApiFailure
from src.api.schemas import ExamResponse, GenerateExamRequest, StudentProfileResponse
from src.api.services import allocate_units
from src.orchestration.exam_assembler import ExamAssembler
from src.orchestration.question_generation import QuestionGenerationService
from src.orchestration.review_service import require_template_regeneration


class ExamService:
    def __init__(self, data, client, *, planner=None, expression_planner=None, validator=None, assembler=None,
                 fake=False, instance_seed=None):
        self.data, self.client, self.fake = data, client, fake
        self.planner = planner or RuleBasedPlanner(data)
        self.expression_planner = expression_planner or ExpressionPlanner()
        self.question_service = QuestionGenerationService(client, validator)
        self.assembler = assembler or ExamAssembler()
        self.engine = TemplateInstantiator()
        self.instance_seed = instance_seed

    def _expression(self, instance, *, eligible_index=0, variant_index=None, previous=None, previous_wording=""):
        registry = self.data.presentation_registry
        if self.fake:
            registry = registry.model_copy(update={"experimental_indirect": False})
        return self.expression_planner.plan_template_expression(instance, registry,
            eligible_index=eligible_index, variant_index=variant_index, previous=previous, previous_wording=previous_wording)

    def _word_template(self, instance, deadline, *, expression=None, previous=None):
        expression = expression or self._expression(instance, previous=previous)
        notes = []
        if not any(p.generate_type == "indirect" for p in expression.template_context.registry.options(instance.template)):
            notes.append(f"Template {instance.template.template_id}: no verified compatible Indirect presentation; using SQL Direct.")
        if self.fake:
            return ValidatedQuestion(expression=expression, content=expression.source_text,
                validation=ValidationResult(status="needs_review", question=expression.source_text,
                    reasons=[*notes, "Demo/Fixture: rendered verified template parameters without Qwen inference."]))
        if not self.client.capacity.acquire(blocking=False):
            raise ApiFailure(503, "QWEN_BUSY", "Qwen is serving another Template request")
        try:
            try:
                candidate = self.question_service.generate(expression, deadline=deadline)
            except ApiFailure as exc:
                if expression.generate_type != "indirect" or exc.code != "INVALID_QWEN_OUTPUT":
                    raise
                # A fresh bounded wording budget on the SAME finalized instance;
                # the common deadline still bounds the entire operation.
                notes.append(f"Indirect wording failed ({exc.code}: {exc.message}); safe SQL Direct fallback on unchanged parameters.")
                direct = self.expression_planner.plan_template_expression(instance, TemplatePresentations(version="fallback"))
                candidate = self.question_service.generate(direct, deadline=deadline)
            candidate.validation.reasons.extend(notes)
            return candidate
        finally:
            self.client.capacity.release()

    def _resolve_sources(self, plan):
        questions = {q.question_id: q for q in self.data.questions}
        definitions = {t.template_id: t for t in self.data.templates}
        result = {}
        for item in plan.questions:
            if item.source_kind == "question":
                result[item.source_key] = questions[item.source_id]
            else:
                definition = definitions.get(item.source_id)
                if definition is None or item.template_instance is None:
                    raise ApiFailure(409, "SOURCE_CHANGED", "Selected Template definition is unavailable")
                try:
                    instance = self.engine.materialize(definition, item.template_instance.parameters)
                except (ValueError, TypeError, KeyError) as exc:
                    raise ApiFailure(409, "SOURCE_CHANGED", "Template instance no longer satisfies its source rules") from exc
                if instance.record != item.template_instance:
                    raise ApiFailure(409, "SOURCE_CHANGED", "Template rules changed since source selection")
                result[item.source_key] = instance
        return result

    def generate(self, request: GenerateExamRequest, profile: StudentProfileResponse) -> ExamResponse:
        blocked, fallback_notes, cache = set(), [], {}
        seed = self.instance_seed if self.instance_seed is not None else secrets.randbits(64)
        deadline = time.monotonic() + (self.client.exam_timeout if self.client else 180)
        # Each failed Template is excluded once. Replanning retains the same
        # allocation, reserves all sources again and never saves a partial exam.
        for _ in range(len(self.data.templates) + 1):
            try:
                plan = self.planner.plan(request, profile, excluded_templates=blocked, seed=seed)
            except ApiFailure as exc:
                if blocked and exc.code == "INSUFFICIENT_QUESTION_BANK":
                    raise ApiFailure(409, exc.code, " ".join([*fallback_notes, exc.message])) from exc
                raise
            sources = self._resolve_sources(plan)
            candidates, failed, eligible_index = [], False, 0
            variant_counts = {}
            previous_template_wording = ""
            for item in plan.questions:
                source = sources[item.source_key]
                if item.source_kind == "question":
                    expression = ExpressionPlanner().plan_expression(source)
                    candidates.append(ValidatedQuestion(expression=expression, content=source.content,
                        validation=ValidationResult(status="needs_review", question=source.content,
                            reasons=["Immutable Question Bank source: original content, answer and solution; Qwen was not invoked."])))
                else:
                    try:
                        expression = self._expression(source, eligible_index=eligible_index, previous_wording=previous_template_wording)
                        variant_key = (item.source_id, expression.generate_type)
                        expression = self._expression(source, eligible_index=eligible_index,
                            variant_index=variant_counts.get(variant_key, 0), previous_wording=previous_template_wording)
                        variant_counts[variant_key] = variant_counts.get(variant_key, 0) + 1
                        if any(p.generate_type == "indirect" for p in expression.template_context.registry.options(source.template)):
                            eligible_index += 1
                        key = (item.source_key, expression.template_context.presentation.fingerprint)
                        if key not in cache:
                            cache[key] = self._word_template(source, deadline, expression=expression)
                        candidates.append(cache[key])
                        previous_template_wording = cache[key].content
                    except ApiFailure as exc:
                        blocked.add(item.source_id)
                        fallback_notes.append(f"Template {item.source_id} wording failed ({exc.code}); trying other Templates or Question Bank fallback.")
                        failed = True
                        break
            if failed:
                continue
            plan.warnings.extend(fallback_notes)
            model = self.client.model if not self.fake and any(i.source_kind == "template" for i in plan.questions) else None
            return self.assembler.assemble(request, profile, plan, sources, candidates, model=model,
                                           backend="fake" if self.fake else "qwen")
        raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK", "No complete exam after bounded Template/Question fallback")

    def regenerate_question(self, exam: ExamResponse, question_id: str) -> ExamResponse:
        question = require_template_regeneration(exam, question_id)
        try:
            self.data.validate_exam_references(exam)
        except ValueError as exc:
            raise ApiFailure(409, "SOURCE_CHANGED", "Stored mathematical or presentation provenance changed") from exc
        if self.fake and exam.provenance.generator != "fake":
            raise ApiFailure(409, "REGENERATION_UNSUPPORTED", "Open this Qwen draft with the Qwen backend to regenerate it")
        definition = next((t for t in self.data.templates if t.template_id == question.source_ref.id), None)
        if definition is None or question.source_digest != template_digest(definition):
            raise ApiFailure(409, "SOURCE_CHANGED", "Template definition changed; generate a new exam")
        try:
            old = self.engine.materialize(definition, question.template_instance.parameters)
        except (ValueError, TypeError, KeyError) as exc:
            raise ApiFailure(409, "SOURCE_CHANGED", "Stored Template parameters no longer satisfy their source rules") from exc
        if (old.record != question.template_instance or old.answer != question.answer
                or [s.explanation for s in question.step_solutions] != old.solution_steps
                or question.skill_ids != definition.skill_ids or question.target_skill_id not in definition.skill_ids
                or question.cognitive_level != definition.cognitive_level or definition.difficulty not in (1, 2)
                or exam.grade_level != definition.grade_level or exam.topic_id != definition.topic_id):
            raise ApiFailure(409, "SOURCE_CHANGED", "Stored Template proof or metadata does not match its definition")
        excluded = {q.template_instance.signature for q in exam.questions if q.template_instance}
        try:
            instances = self.engine.instances(definition, 1, seed=f"{old.record.signature}:{exam.revision}", excluded=excluded)
        except (ValueError, TypeError, KeyError) as exc:
            raise ApiFailure(409, "TEMPLATE_INSTANTIATION_FAILED", "Cannot produce a different valid Template instance") from exc
        source = instances[0] if instances else old
        previous = question.template_presentation or self.data.presentation_registry.record(definition)
        expression = self._expression(source, previous=previous, previous_wording=question.content_latex)
        if not instances and expression.template_context.presentation.presentation_id == previous.presentation_id:
            raise ApiFailure(409, "TEMPLATE_INSTANTIATION_FAILED", "No different mathematical instance or compatible presentation is available")
        candidate = self._word_template(source, time.monotonic() + (self.client.exam_timeout if self.client else 180), expression=expression)
        if not instances and candidate.expression.template_context.presentation == previous:
            raise ApiFailure(409, "TEMPLATE_INSTANTIATION_FAILED", "Presentation fallback produced no new instance or presentation")
        value = exam.model_dump(mode="python")
        value.update(status="pending_teacher_review", teacher_review=None, revision=exam.revision + 1)
        for item in value["questions"]:
            item["validation"]["teacher_approved"] = False
            if item["question_id"] == question_id:
                units = round(item["max_score"] * 4)
                item.update(question_id="QT_" + uuid4().hex, content_latex=candidate.content,
                    generate_type=candidate.expression.generate_type,
                    template_presentation=candidate.expression.template_context.presentation.model_dump(mode="python"),
                    answer=source.answer.model_dump(mode="python"), template_instance=source.record.model_dump(mode="python"),
                    step_solutions=[{"step_number": i, "explanation": text, "score": part / 4}
                        for i, (text, part) in enumerate(zip(source.solution_steps, allocate_units(units, len(source.solution_steps))), 1)],
                    rubric=[{"criteria": "Áp dụng đúng quy tắc và tham số; giải thích và kết luận đúng.", "sub_score": units / 4}],
                    validation={"auto_status": "not_evaluated" if self.fake else "needs_review", "teacher_approved": False,
                                "review_notes": [*candidate.validation.reasons,
                                    "Template instance and presentation provenance rechecked; teacher review required."]})
        value["provenance"] = {"generator": "fake" if self.fake else "qwen", "model": None if self.fake else self.client.model}
        return ExamResponse.model_validate(value)
