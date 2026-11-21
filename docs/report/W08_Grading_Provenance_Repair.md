# Frozen-grading provenance repair — 2026-11-20

Repository: `MIRA/adaptive-learning`. This repair changes the provenance guard,
test-only reference and documentation. Application grading, transport, storage,
API and UI code are unchanged. No commit or push was performed.

## Confirmed root cause and source identity

The supplied failure lists hash mismatches without recording the failing Python
version. The repository's README supports Python 3.11+; CI still uses Python 3.11
and runs `pytest -q`. No CI Python version was changed.

The original manifest did not record its generating interpreter/serializer.
The integration report records local Python 3.13.13; on that exact available
interpreter all **38/38** original-source `ast.dump(include_attributes=False)`
hashes reproduce the unchanged manifest. On available Python **3.11.15** and
**3.12.7**, only **10/38** reproduce it: the same 28-definition mismatch pattern
as the supplied failure. The exact previous pytest test passes on 3.13.13.
Default `python` here is 3.12.7 without pytest; that command initially failed
with `No module named pytest`, which is separate from the reproduced hash issue.

I verified the authoritative sibling file before copying any reference:

```text
Original: ../MIRA_Standalone_AI_Grading_Test_v2/run_test.py
Revision: R2026-11-17-scoped-skill-guidance-v11
SHA-256: f5d2b37ff9bf2a807d0107946c473a68f397b19b335feae8c3c5bcfd76d0cc0c
Test-only copy: tests/fixtures/grading_v11/frozen_standalone_v11.py.txt
```

The hash agrees with the original manifest/current-state provenance, and the copy
is byte-for-byte identical, not reconstructed from production code. Existing
generation/extraction scripts were searched; no persisted grading manifest
generator existed in the checkout. The previous extraction was a one-off step.
The sibling source remains unchanged, and no production runtime/test execution
now depends on that sibling being available.

The demonstrated serialization difference is **empty list display**:

```text
Python 3.12 default (representative fragment from clean):
arguments(posonlyargs=[], args=[arg(arg='text')], kwonlyargs=[], kw_defaults=[], defaults=[])
Call(..., keywords=[])
FunctionDef(..., decorator_list=[], type_params=[])

Python 3.13 default, from the same parsed source:
arguments(args=[arg(arg='text')])
Call(...)
FunctionDef(...)
```

Using Python 3.13's `ast.dump(..., show_empty=True)` reproduces Python 3.12's
default dump **exactly for all 38 definitions**. Python 3.11 also lacks the
`FunctionDef.type_params` field present in 3.12/3.13. These facts make a stored
default AST dump hash unsuitable as a cross-version identity. Removing location
attributes does not remove this version sensitivity.

## Readable structural comparisons

I parsed both the verified original and integrated modules under the **same**
interpreter before changing the test. There were zero mismatching definitions
after accounting for the precise existing injections. The repaired guard repeats
this comparison on 3.11.15, 3.12.7 and 3.13.13.

| Definition | Frozen → integrated structural difference before undoing injection | After the authorized undo | Representative serialization-only difference |
|---|---|---|---|
| `clean` | None | Equal | Empty positional-only/keyword-only/default/Call keywords/decorator/type parameter lists displayed in 3.12 and omitted in 3.13 |
| `initial_instructions` | None | Equal | Empty argument/default lists and `allowed_skill_ids(...)` call keywords; condition and prompt format arguments unchanged |
| `validate_case` | None | Equal | Empty Call args/keywords and branch lists; all comparisons, overrides, source checks, docstrings and return paths unchanged |
| `call_model` | Adds keyword-only `request_fn=None`; replaces only the original transport target at the env assignment | Equal | Empty list fields elsewhere in the function; exception handling and response checks unchanged |
| `grade_question` | Adds keyword-only `client=None`; replaces only the initial/repair call dispatch target | Equal | Empty call/branch lists; defaults, repair bounds, stop conditions and formatter data unchanged |
| `exam_payload` | None | Equal | Empty call keyword/default/comprehension/branch lists; assessed actions, errors, uncertainty and whole-exam feedback unchanged |

The only permitted statement differences, including their original arguments, are:

```python
# grade_question, original:
call = call_model(request_payload, timeout, 'initial' if not attempt else 'repair')
# integrated:
call = (client.call_model if client is not None else call_model)(
    request_payload, timeout, 'initial' if not attempt else 'repair')

# call_model, original:
env = request('/api/generate', payload, timeout)
# integrated:
env = (request_fn or request)('/api/generate', payload, timeout)
```

No annotation, function docstring, prompt/regex string, constant, control-flow,
grading condition, default, arithmetic operation, stopping or repair behavior
drift was found. Integration module imports/headers, transport helpers and blank/
output adaptation remain separate from the frozen definitions. Formatting and
comments outside literal strings are intentionally outside AST identity.

## Repair and why the guard remains meaningful

`tools/grading_provenance.py` implements **`same-interpreter-ast-v1`**. It first
validates the raw reference SHA-256 and grading revision, then parses the pinned
reference and both integrated modules with the running interpreter. All 38
definitions remain checked. There is **no stable/canonical AST serializer** here:
no fields are indiscriminately stripped, and no version-specific empty fields
need normalization because both sides share the current parser/dumper. The old
38 hashes remain unchanged in `ast_sha256` as historical evidence and the frozen
definition inventory; current expected structure comes only from the independently
verified snapshot. It is never generated from current production definitions.

The reference is `.py.txt` data, parsed only, never imported or executed. Its full
original contents are preserved to verify raw identity, including original
benchmark helpers; none of those helpers enter application runtime. A targeted
`.gitattributes` entry disables newline conversion to preserve the original bytes.
The manifest records the check version, reference path, complete module inventory,
explicit transport-only integration definitions and narrow injection policy.

Injection validation checks the entire expected signature before removing **only**
the added unannotated keyword-only `client=None` / `request_fn=None`. It identifies
the unique original complete call statement in the frozen function, checks the
exact complete injected statement at that same AST path, then restores only that
statement. It never strips arbitrary keyword-only arguments or rewrites all
assignments named `call`/`env`. Additional defaults, annotations, arguments, altered
targets, moved calls and extra assignments fail the guard.

Diagnostics name missing, unexpected, duplicate or mismatching definitions and
show a first named AST difference with bounded string excerpts instead of pages
of hash dictionaries. Example for changing the arithmetic addition operator:

```text
src/grading/engine.py: mismatching definition value: value.body[2].body[1].body[0].value.op: frozen Add, integrated Sub
```

The original pytest test name is retained. New mutation tests exercise acceptance
of legitimate extraction, comments and formatting, plus rejection of changed
prompt text/whitespace, regexes, comparison/operators, repair limits/budgets/defaults,
docstrings/annotations, missing/unexpected/duplicate definitions, raw snapshot
changes and unauthorized injection modifications.

## Changed files

| Path | Purpose |
|---|---|
| `.gitattributes` | Preserve exact bytes of the authoritative test-only snapshot |
| `docs/notes/grading_source_manifest.json` | Record same-interpreter reference/inventory/injection policy; retain every existing digest |
| `tests/fixtures/grading_v11/frozen_standalone_v11.py.txt` | Add verified independent original source as test data |
| `tests/fixtures/grading_v11/README.md` | Explain raw source identity and reference-only use |
| `tools/grading_provenance.py` | Shared stdlib verifier, precise injection undo and concise diagnostics; CLI for cross-version checks |
| `tests/grading/test_engine.py` | Retain failing test name, invoke the repaired guard, leave replay tests intact |
| `tests/grading/test_provenance.py` | Add 22 meaningful mutation tests, runnable without application dependencies |
| `docs/notes/W08_Grading_Current_State.md` | Record actual diagnosis and provenance method |
| `docs/design/W08_AI_Grading_Design_Final.md` | Append provenance correction without changing grading/product design |
| `docs/report/W08_Grading_Provenance_Repair.md` | This diagnostic and verification handoff |

`src/grading/engine.py`, `src/grading/qwen_client.py`, API/storage/UI, dependencies
and CI workflow are unchanged. No JSON viewer/download or grading feature was added.

## Verification

The original failing test command is unchanged:

```bash
python -m pytest tests/grading/test_engine.py::test_all_extracted_definitions_match_frozen_ast_except_explicit_injection -q
python -m pytest tests/grading -q
python -m pytest -q
```

The test-only guard and its mutation coverage can be verified without installing
FastAPI/Pydantic or executing the runtime:

```bash
python tools/grading_provenance.py
python -m unittest tests.grading.test_provenance -q
```

Actual results on this checkout:

| Interpreter / check | Actual result |
|---|---|
| CPython 3.13.13, exact originally failing pytest test | **1 passed**, 0.50 s |
| CPython 3.13.13, exact test plus mutation module | **23 passed**, 3.91 s |
| CPython 3.13.13, `python -m pytest tests/grading -q` | **88 passed**, 14.29 s; one existing Starlette warning |
| CPython 3.13.13, full `python -m pytest -q` / current CI test command | **692 passed**, 59.40 s; no skips/failures; same existing Starlette warning |
| CPython 3.11.15, guard CLI | **38 definitions match** |
| CPython 3.11.15, pytest mutation module | **22 passed, 14 subtests passed**, 3.60 s |
| CPython 3.12.7, guard CLI | **38 definitions match** |
| CPython 3.12.7, unittest mutation module | **22 tests passed**, 3.841 s |
| CPython 3.13.13, guard CLI | **38 definitions match** |
| Ruff on three changed Python test/tool files | Passed |
| `git diff --check` | Passed; Git reports normal LF→CRLF checkout conversion for the edited test file |

The 20 original grading replays remain unchanged and passed, including correct,
method/constraint and arithmetic errors, incomplete work, alternate valid methods,
invalid evidence/uncertain cases, first-error stopping and one-repair behavior.
Full pytest also executed the existing grading API/storage tests and both UI
workflow checks (Node was available on PATH). No tests or CI checks were weakened.

Exact local runtime used for the three required pytest commands:
`D:/HCMUS/TDTT/TH/Main_Project/.venv/Scripts/python.exe` (3.13.13). The suite commands
also used `-B -p no:cacheprovider` and fresh dedicated basetemps
`.pytest_tmp_mira/provenance_grading_20261120` and
`.pytest_tmp_mira/provenance_full_20261120`. These scratch directories are ignored.
Python 3.11.15 was `D:/Miniconda/envs/aic_gdgoc/python.exe`; Python 3.12.7 was the
default `D:/VSCode/ucrt64/bin/python.exe`.

Cross-version limitation: the **guard and all 22 mutation tests** were verified on
3.11/3.12/3.13; the **full application/replay suite ran only on 3.13.13**. The local
3.11 environment lacks FastAPI/Pydantic/HTTPX/Uvicorn and the 3.12 environment lacks
pytest/application dependencies. No dependency installation or CI-version change
was used to hide this. Remote Ubuntu CI and Python 3.14+ were not executed here.
The supplied original failure's exact interpreter remains unrecorded.

Every historical manifest digest was compared with Git HEAD and is unchanged.
The new reference's raw hash and bytes match the independently verified sibling;
both integrated production files and `.github/workflows/ci.yml` have no diff.
No live Qwen inference was performed for this repair. Recorded replay tests are
behavior regressions, not new model accuracy evidence.

## Suggested English commit message

```text
Fix cross-version frozen grading provenance checks with a pinned source snapshot
```
