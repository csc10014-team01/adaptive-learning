"""Mutation tests for the frozen-source guard; standard-library-only for 3.11+.

Can run through pytest or: python -m unittest tests.grading.test_provenance -v
No reference/application execution, provider calls or runtime storage is needed.
"""

import ast
import copy
import json
import unittest
from pathlib import Path

from tools.grading_provenance import ProvenanceError, verify_sources

ROOT = Path(__file__).resolve().parents[2]
ENGINE = "src/grading/engine.py"
CLIENT = "src/grading/qwen_client.py"


class ProvenanceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "docs/notes/grading_source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        cls.reference = (
            ROOT / cls.manifest["structural_comparison"]["reference_snapshot"]
        ).read_bytes()
        cls.sources = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in cls.manifest["structural_comparison"]["modules"]
        }

    def verify(self, sources):
        verify_sources(self.reference, sources, self.manifest)

    def changed(self, module, name, mutate):
        tree = ast.parse(self.sources[module])
        for definition in tree.body:
            definition_name = (
                definition.name
                if isinstance(definition, (ast.FunctionDef, ast.ClassDef))
                else (
                    definition.targets[0].id
                    if isinstance(definition, ast.Assign)
                    and isinstance(definition.targets[0], ast.Name)
                    else None
                )
            )
            if definition_name == name:
                mutate(definition)
                return {**self.sources, module: ast.unparse(tree)}
        self.fail("Mutation target not found: " + name)

    def rejected(self, sources, diagnostic):
        with self.assertRaisesRegex(ProvenanceError, diagnostic):
            self.verify(sources)

    def test_authorized_extraction_and_both_injections_match(self):
        self.verify(self.sources)
        self.assertEqual(len(self.manifest["ast_sha256"]), 38)

    def test_comments_formatting_and_quote_style_are_ignored(self):
        formatted = {
            path: "# An ordinary comment.\n\n" + ast.unparse(ast.parse(source)) + "\n"
            for path, source in self.sources.items()
        }
        self.verify(formatted)

    def test_prompt_text_change_fails_with_string_excerpt(self):
        changed = self.changed(
            ENGINE,
            "INSTRUCTIONS",
            lambda n: setattr(
                n.value, "value", n.value.value + "Different grading instruction."
            ),
        )
        self.rejected(changed, r"mismatching definition INSTRUCTIONS.*at character")

    def test_prompt_whitespace_is_not_normalized(self):
        changed = self.changed(
            ENGINE,
            "INSTRUCTIONS",
            lambda n: setattr(
                n.value,
                "value",
                n.value.value.replace("COMPLETE student", "COMPLETE  student"),
            ),
        )
        self.rejected(changed, "mismatching definition INSTRUCTIONS")

    def test_regex_whitespace_is_not_normalized(self):
        def mutate(definition):
            pattern = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.Constant) and n.value == r"\s+"
            )
            pattern.value = r"\s*"

        self.rejected(
            self.changed(ENGINE, "clean", mutate), "mismatching definition clean"
        )

    def test_grading_comparison_change_fails(self):
        def mutate(definition):
            comparison = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.NotEq)
            )
            comparison.ops[0] = ast.Eq()

        self.rejected(
            self.changed(ENGINE, "validate_case", mutate),
            r"validate_case.*ops\[0\].*NotEq.*Eq",
        )

    def test_arithmetic_operator_change_fails(self):
        def mutate(definition):
            operation = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
            )
            operation.op = ast.Sub()

        self.rejected(self.changed(ENGINE, "value", mutate), r"value.*op.*Add.*Sub")

    def test_repair_limit_condition_change_fails(self):
        def mutate(definition):
            definition.body[0].test.comparators[0].elts.append(ast.Constant(value=2))

        self.rejected(
            self.changed(ENGINE, "grade_question", mutate),
            "mismatching definition grade_question",
        )

    def test_grading_defaults_cannot_hide_behind_injection(self):
        for index, value in enumerate((1201, 8193, 121, 2)):
            with self.subTest(default_index=index):

                def mutate(definition):
                    definition.args.defaults[index] = ast.Constant(value=value)

                self.rejected(
                    self.changed(ENGINE, "grade_question", mutate),
                    "grade_question: unauthorized injection signature",
                )

    def test_extraction_repair_budget_change_fails(self):
        def mutate(definition):
            budget = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.Constant) and n.value == 160
            )
            budget.value = 320

        self.rejected(
            self.changed(ENGINE, "make_repair_payload", mutate),
            "mismatching definition make_repair_payload",
        )

    def test_unexpected_keyword_only_argument_fails_for_both_injections(self):
        for module, name in ((ENGINE, "grade_question"), (CLIENT, "call_model")):
            with self.subTest(definition=name):

                def mutate(definition):
                    definition.args.kwonlyargs.append(ast.arg(arg="override"))
                    definition.args.kw_defaults.append(ast.Constant(value=None))

                self.rejected(
                    self.changed(module, name, mutate),
                    name + ": unauthorized injection signature",
                )

    def test_injected_parameter_name_default_and_annotation_are_checked(self):
        for module, name in ((ENGINE, "grade_question"), (CLIENT, "call_model")):
            for mutation in ("name", "default", "annotation"):
                with self.subTest(definition=name, mutation=mutation):

                    def mutate(definition):
                        if mutation == "name":
                            definition.args.kwonlyargs[-1].arg = "other"
                        elif mutation == "default":
                            definition.args.kw_defaults[-1] = ast.Constant(value=False)
                        else:
                            definition.args.kwonlyargs[-1].annotation = ast.Name(
                                id="object", ctx=ast.Load()
                            )

                    self.rejected(
                        self.changed(module, name, mutate),
                        name + ": unauthorized injection signature",
                    )

    def test_unauthorized_client_call_target_fails(self):
        def mutate(definition):
            attribute = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id == "client"
            )
            attribute.attr = "other_method"

        self.rejected(
            self.changed(ENGINE, "grade_question", mutate),
            "grade_question: unauthorized injected call",
        )

    def test_unauthorized_request_function_target_fails(self):
        def mutate(definition):
            target = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.BoolOp)
                and isinstance(n.values[0], ast.Name)
                and n.values[0].id == "request_fn"
            )
            target.values[1].id = "other_request"

        self.rejected(
            self.changed(CLIENT, "call_model", mutate),
            "call_model: unauthorized injected call",
        )

    def test_injected_call_arguments_are_checked(self):
        def mutate(definition):
            path = next(
                n
                for n in ast.walk(definition)
                if isinstance(n, ast.Constant) and n.value == "/api/generate"
            )
            path.value = "/api/wrong"

        self.rejected(
            self.changed(CLIENT, "call_model", mutate),
            "call_model: unauthorized injected call",
        )

    def test_call_locations_cannot_move(self):
        def mutate(definition):
            definition.body.insert(0, ast.Pass())

        self.rejected(
            self.changed(ENGINE, "grade_question", mutate),
            "grade_question:.*authorized|grade_question: unauthorized",
        )

    def test_other_call_or_env_assignments_are_never_silently_rewritten(self):
        for module, name, target in (
            (ENGINE, "grade_question", "call"),
            (CLIENT, "call_model", "env"),
        ):
            with self.subTest(definition=name):

                def mutate(definition):
                    definition.body.append(
                        ast.parse(target + " = unauthorized()").body[0]
                    )

                self.rejected(
                    self.changed(module, name, mutate), "mismatching definition " + name
                )

    def test_docstring_and_annotations_are_preserved(self):
        def docstring(definition):
            definition.body[0].value.value += " Changed claim."

        self.rejected(
            self.changed(ENGINE, "validate_case", docstring),
            "mismatching definition validate_case",
        )
        self.rejected(
            self.changed(
                ENGINE,
                "clean",
                lambda n: setattr(n, "returns", ast.Name(id="str", ctx=ast.Load())),
            ),
            "mismatching definition clean",
        )

    def test_missing_and_unexpected_definitions_have_concise_diagnostics(self):
        tree = ast.parse(self.sources[ENGINE])
        tree.body = [
            n
            for n in tree.body
            if not isinstance(n, ast.FunctionDef) or n.name != "clean"
        ]
        self.rejected(
            {**self.sources, ENGINE: ast.unparse(tree)}, "missing definitions: clean"
        )
        self.rejected(
            {
                **self.sources,
                ENGINE: self.sources[ENGINE] + "\ndef unauthorized(): pass\n",
            },
            "unexpected definitions: unauthorized",
        )

    def test_duplicate_definition_fails(self):
        self.rejected(
            {
                **self.sources,
                ENGINE: self.sources[ENGINE] + "\ndef clean(text): return text\n",
            },
            "duplicate definition clean",
        )

    def test_raw_snapshot_hash_is_distinct_from_structural_comparison(self):
        with self.assertRaisesRegex(ProvenanceError, "source SHA-256 mismatch"):
            verify_sources(
                self.reference + b"\n# Even a comment changes raw identity\n",
                self.sources,
                self.manifest,
            )

    def test_module_inventory_cannot_silently_drop_a_frozen_definition(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["structural_comparison"]["modules"][ENGINE].remove("clean")
        with self.assertRaisesRegex(
            ProvenanceError, "every frozen definition exactly once"
        ):
            verify_sources(self.reference, self.sources, manifest)


if __name__ == "__main__":
    unittest.main()
