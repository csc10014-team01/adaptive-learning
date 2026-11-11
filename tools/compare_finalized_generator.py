"""Read committed reference code in memory and compare reproducible behavior.

Run from the target repository with --source /path/to/old/repo. Neither repository
nor any database is written. Results are printed as JSON.
"""

import argparse
import ast
import importlib
import importlib.abc
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "1a7147cd4671b42507ac5c5d6a3f525262eb903d"


def reference_text(source, relative):
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={source.as_posix()}",
            "show",
            f"{COMMIT}:{relative}",
        ],
        cwd=source,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")


def paths(text, relative):
    if relative == "src/api/data_adapter.py":
        text = text.replace("parents[2]", "parents[3]").replace(
            'ROOT.parents[1] / "pre-work" / "data"', 'ROOT / "data"'
        )
    elif relative == "src/api/m3_adapter.py":
        text = text.replace(
            'ROOT.parents[1] / "pre-work/data/sample/memory/student_profiles_sample.db"',
            'ROOT / "data/sample/memory/student_profiles_sample.db"',
        )
    elif relative == "src/ai/template_presentations.py":
        text = text.replace("parents[2]", "parents[3]")
    return text


class WithoutImports(ast.NodeTransformer):
    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None


def import_bindings(text):
    result = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom):
            result.extend(
                ("from", node.module, node.level, alias.name, alias.asname or "")
                for alias in node.names
            )
        elif isinstance(node, ast.Import):
            result.extend(
                ("import", "", 0, alias.name, alias.asname or "")
                for alias in node.names
            )
    return sorted(result)


class ReferenceLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, modules):
        self.modules = modules

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.modules:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        filename, text = self.modules[module.__name__]
        module.__file__ = str(filename)
        exec(compile(text, str(filename), "exec"), module.__dict__)  # noqa: S102 -- Explicit trusted commit, read-only local comparison.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    manifest = json.loads(
        (ROOT / "docs/report/generator_source_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    modules, checked = {}, []
    for destination, record in manifest["files"].items():
        if not destination.startswith("src/exam_generator/"):
            continue
        original = paths(
            reference_text(args.source, record["source"]), record["source"]
        )
        integrated = (
            (ROOT / destination)
            .read_text(encoding="utf-8")
            .replace("src.exam_generator.", "src.")
        )
        assert import_bindings(original) == import_bindings(integrated), destination
        # Import order/line layout can change through Ruff. Every executable
        # statement, constant, prompt and policy remains identical after mapping.
        assert ast.dump(WithoutImports().visit(ast.parse(original))) == ast.dump(
            WithoutImports().visit(ast.parse(integrated))
        ), destination
        name = record["source"][4:-3].replace("/", ".")
        modules["mira_reference." + name] = (
            ROOT / destination,
            original.replace("from src.", "from mira_reference.").replace(
                "import src.", "import mira_reference."
            ),
        )
        checked.append(destination)
    for name in (
        "mira_reference",
        *(
            f"mira_reference.{p}"
            for p in ("adaptation", "ai", "api", "orchestration", "validation")
        ),
    ):
        package = types.ModuleType(name)
        package.__path__ = []
        sys.modules[name] = package
    sys.meta_path.insert(0, ReferenceLoader(modules))
    cases = {
        "no_data": [(None, 0)] * 9,
        "partial": [(1.0, 1)] * 9,
        "mixed": [(None, 0), (3.9, 4)] + [(1.0, 1)] * 7,
        "one_weak": [(0.0, 6)] + [(3.25, 5)] * 8,
        "two_weak": [(0.5, 6), (1.75, 4)] + [(3.25, 5)] * 7,
        "achieved": [(4.0, 5)] * 9,
    }
    comparisons = 0
    for related in (False, True):
        for case, rows in cases.items():
            for count in (1, 4, 7, 10):
                outputs = []
                for namespace in ("mira_reference", "src.exam_generator"):

                    def load(name, namespace=namespace):
                        return importlib.import_module(namespace + "." + name)

                    schemas = load("api.schemas")
                    data = load("api.m3_adapter").M3DataAdapter()
                    profile = schemas.StudentProfileResponse(
                        student_id="ISOLATED",
                        name="Reference comparison",
                        grade_level=10,
                        skill_mastery=[
                            {
                                "skill_id": f"A{i:03}",
                                "mastery_score": score,
                                "evidence_count": evidence,
                            }
                            for i, (score, evidence) in enumerate(rows, 1)
                        ],
                        learning_history=[],
                    )
                    request = schemas.GenerateExamRequest(
                        student_id="ISOLATED",
                        selected_topic_ids=["combinatorics"],
                        total_questions=count,
                        duration_minutes=45,
                    )
                    relationships = (
                        load("adaptation.skill_relationships").SkillRelationships.load(
                            ROOT / "config/skill_relationships_a001_a009.json"
                        )
                        if related
                        else None
                    )
                    planner = load("adaptation.planner").RuleBasedPlanner(
                        data, relationships=relationships
                    )
                    plan = planner.plan(request, profile, seed=42).model_dump(
                        mode="json"
                    )
                    exam = (
                        load("orchestration.exam_service")
                        .ExamService(
                            data, None, fake=True, planner=planner, instance_seed=42
                        )
                        .generate(request, profile)
                    )
                    value = exam.model_dump(mode="json")
                    value.pop("exam_id")
                    for question in value["questions"]:
                        question.pop("question_id")
                    outputs.append((plan, value))
                assert outputs[0] == outputs[1], (case, count, related)
                comparisons += 1
    print(
        json.dumps(
            {
                "reference_commit": COMMIT,
                "core_modules_ast_equal": len(checked),
                "plan_and_exam_comparisons_passed": comparisons,
                "seed": 42,
                "cases": list(cases),
                "question_counts": [1, 4, 7, 10],
                "relationship_modes": ["off", "on"],
                "inference": "fake; no claim about real Qwen wording",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
