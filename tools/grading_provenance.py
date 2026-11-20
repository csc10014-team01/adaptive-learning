"""Check frozen grading definitions against a byte-pinned, test-only source snapshot.

Both sides are parsed/dumped by this interpreter. No cross-version AST hash or
canonicalization is used. This module uses only the standard library and never
imports/executes the reference, application code, benchmarks or Ollama.
"""

import argparse
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPARISON_VERSION = "same-interpreter-ast-v1"
INJECTIONS = {
    "grade_question": (
        "client",
        "call = call_model(request_payload, timeout, 'initial' if not attempt else 'repair')",
        "call = (client.call_model if client is not None else call_model)(request_payload, timeout, 'initial' if not attempt else 'repair')",
    ),
    "call_model": (
        "request_fn",
        "env = request('/api/generate', payload, timeout)",
        "env = (request_fn or request)('/api/generate', payload, timeout)",
    ),
}


class ProvenanceError(ValueError):
    """A source identity, inventory, injection or structural mismatch."""


def dump(node):
    return ast.dump(node, include_attributes=False)


def definitions(source, label):
    result = {}
    for node in ast.parse(source, filename=label).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, (ast.Import, ast.ImportFrom)) or (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        else:
            raise ProvenanceError(
                f"{label}: unexpected top-level {type(node).__name__}"
            )
        if name in result:
            raise ProvenanceError(f"{label}: duplicate definition {name}")
        result[name] = node
    return result


def first_difference(expected, actual, path):
    """First named structural path, without location attributes or giant dumps."""
    if type(expected) is not type(actual):
        return f"{path}: frozen {type(expected).__name__}, integrated {type(actual).__name__}"
    if isinstance(expected, ast.AST):
        for field, value in ast.iter_fields(expected):
            if not hasattr(actual, field):
                return f"{path}.{field}: missing field"
            difference = first_difference(
                value, getattr(actual, field), f"{path}.{field}"
            )
            if difference:
                return difference
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: frozen length {len(expected)}, integrated length {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif expected != actual:
        if isinstance(expected, str):
            index = next(
                (i for i, (a, b) in enumerate(zip(expected, actual)) if a != b),
                min(len(expected), len(actual)),
            )
            start, end = max(0, index - 35), index + 65
            return f"{path} at character {index}: frozen {expected[start:end]!r}, integrated {actual[start:end]!r}"
        return f"{path}: frozen {expected!r}, integrated {actual!r}"
    return None


def matching_paths(node, target, path=()):
    if isinstance(node, ast.AST):
        if dump(node) == dump(target):
            yield path
        for field, value in ast.iter_fields(node):
            yield from matching_paths(value, target, path + (field,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from matching_paths(value, target, path + (index,))


def at_path(node, path):
    for field in path:
        node = node[field] if isinstance(field, int) else getattr(node, field)
    return node


def undo_authorized_injection(reference, integrated, name):
    parameter, original_code, injected_code = INJECTIONS[name]
    actual = copy.deepcopy(integrated)
    if not isinstance(reference, ast.FunctionDef) or not isinstance(
        actual, ast.FunctionDef
    ):
        raise ProvenanceError(f"{name}: injection requires the frozen FunctionDef")
    expected_args = copy.deepcopy(reference.args)
    expected_args.kwonlyargs.append(ast.arg(arg=parameter))
    expected_args.kw_defaults.append(ast.Constant(value=None))
    if dump(actual.args) != dump(expected_args):
        raise ProvenanceError(
            f"{name}: unauthorized injection signature; "
            + first_difference(expected_args, actual.args, name + ".args")
        )
    # Remove only the single verified, unannotated keyword-only parameter = None.
    actual.args.kwonlyargs.pop()
    actual.args.kw_defaults.pop()
    original = ast.parse(original_code).body[0]
    injected = ast.parse(injected_code).body[0]
    paths = list(matching_paths(reference, original))
    if len(paths) != 1:
        raise ProvenanceError(f"{name}: expected exactly one frozen transport call")
    path = paths[0]
    try:
        statement = at_path(actual, path)
    except (AttributeError, IndexError, TypeError) as exc:
        raise ProvenanceError(
            f"{name}: injected call moved from its authorized location {path}"
        ) from exc
    if dump(statement) != dump(injected):
        raise ProvenanceError(
            f"{name}: unauthorized injected call; "
            + first_difference(injected, statement, name + ".transport_call")
        )
    parent = at_path(actual, path[:-1])
    parent[path[-1]] = copy.deepcopy(original)
    return actual


def verify_sources(reference_bytes, sources, manifest):
    """Validate identity/inventory and compare all 38 definitions, on this Python."""
    if hashlib.sha256(reference_bytes).hexdigest() != manifest["source_sha256"]:
        raise ProvenanceError("Frozen reference source SHA-256 mismatch")
    spec = manifest["structural_comparison"]
    if spec["version"] != COMPARISON_VERSION:
        raise ProvenanceError("Unsupported frozen structural comparison version")
    # Parse the full verified source, but collect only the frozen runtime inventory.
    reference = {}
    inventory = set(manifest["ast_sha256"])
    for node in ast.parse(reference_bytes.decode("utf-8")).body:
        name = (
            node.name
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            else (
                node.targets[0].id
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                else None
            )
        )
        if name in inventory:
            if name in reference:
                raise ProvenanceError(f"Frozen reference: duplicate definition {name}")
            reference[name] = node
    if set(reference) != inventory:
        raise ProvenanceError(
            "Frozen reference missing definitions: "
            + ", ".join(sorted(inventory - set(reference)))
        )
    if (
        ast.literal_eval(reference["GRADING_REVISION"].value)
        != manifest["engine_revision"]
    ):
        raise ProvenanceError("Frozen reference grading revision mismatch")
    module_names = [name for names in spec["modules"].values() for name in names]
    if len(module_names) != len(set(module_names)) or set(module_names) != inventory:
        raise ProvenanceError(
            "Manifest module inventory must contain every frozen definition exactly once"
        )
    if set(sources) != set(spec["modules"]):
        raise ProvenanceError("Integrated module inventory mismatch")
    errors = []
    for module, names in spec["modules"].items():
        actual = definitions(sources[module], module)
        allowed = set(names) | set(spec["integration_only_definitions"].get(module, []))
        missing, unexpected = allowed - set(actual), set(actual) - allowed
        if missing:
            errors.append(
                f"{module}: missing definitions: {', '.join(sorted(missing))}"
            )
        if unexpected:
            errors.append(
                f"{module}: unexpected definitions: {', '.join(sorted(unexpected))}"
            )
        for name in sorted(set(names) & set(actual)):
            try:
                checked = (
                    undo_authorized_injection(reference[name], actual[name], name)
                    if name in INJECTIONS
                    else actual[name]
                )
                if dump(reference[name]) != dump(checked):
                    errors.append(
                        f"{module}: mismatching definition {name}: "
                        + first_difference(reference[name], checked, name)
                    )
            except ProvenanceError as exc:
                errors.append(f"{module}: {exc}")
    if errors:
        raise ProvenanceError(
            "Frozen grading provenance check failed:\n" + "\n".join(errors)
        )


def verify_repository(root=ROOT):
    manifest = json.loads(
        (root / "docs/notes/grading_source_manifest.json").read_text(encoding="utf-8")
    )
    reference = (
        root / manifest["structural_comparison"]["reference_snapshot"]
    ).read_bytes()
    sources = {
        name: (root / name).read_text(encoding="utf-8")
        for name in manifest["structural_comparison"]["modules"]
    }
    verify_sources(reference, sources, manifest)
    return len(manifest["ast_sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        count = verify_repository()
    except ProvenanceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"Frozen grading provenance: {count} definitions match on Python {sys.version.split()[0]} ({COMPARISON_VERSION})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
