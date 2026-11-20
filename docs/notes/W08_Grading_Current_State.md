# AI grading integration — current state / changelog

Date: **2026-11-20 (Asia/Saigon)**. Owner: **Phạm Yến Trân — AI & Algorithm Lead**.

## Integration W08-2026-11-20-v1

The existing FastAPI application now hosts protected asynchronous grading jobs and
a separate `/grading` UI, launched with `python -m src.ui --grading`. Experimental
multi-question context and original raw answers work independently of canonical
submissions. One bounded local worker uses a separate transactional runtime store.
Completed jobs can include uncertain questions; original inputs and partial results
survive interruption. Unfinished work is marked interrupted at first grading access
after restart, never automatically resumed. A local file lease rejects concurrent
processes using the same store. Deployment remains one process/worker.

The inherited engine is **R2026-11-17-scoped-skill-guidance-v11**. Its verified
standalone source SHA-256 is
`f5d2b37ff9bf2a807d0107946c473a68f397b19b335feae8c3c5bcfd76d0cc0c`.
It is extracted into `src/grading/engine.py` and `qwen_client.py`; only client/request
injection and configurable transport origin differ structurally. Prompt order,
proposal schema, source/arithmetic checks, one-repair policy, stopping and compact
formatting are preserved. No runtime benchmark directory, gold or evaluation logic.
Later rejected translation candidates are not included. This integration revision
does not constitute a new grading algorithm or reliability baseline.

Integration additions are explicit blank-answer handling, validated request/context
adapters, exact server-owned approved revision lookup, job metadata/storage,
neutral issue codes, deterministic whole-exam feedback, optional debug retention,
and safe UI input/polling/reopening/downloading. `requires_teacher` and
`teacher_comment` are legacy output fields only. No teacher result editing, points,
PCM/EAP, observed levels, root/propagated classification or profile updates.

Canonical database inspection confirms `student_answer_attempt` now exists but
contains zero records. All 121 bank question rubrics use step/description without
per-step skill IDs or stable rubric IDs. Three of eighteen template rubrics are
invalid JSON. The 40 historical `test_questions.AI` values are integer flags, not
answers. Runtime exam snapshots use criteria/sub_score and currently contain no
approved revisions. Approved mode therefore reports actionable context-not-ready
errors when required data is insufficient; a future canonical submission adapter
is an explicit Protocol boundary, not implemented access or a migration.

Verification evidence: all 20 saved selected-v11 P/N requests and compact outcomes
replay identically; frozen AST hashes also match after normalizing the two injection
changes. Offline integration includes auth/context/IDs, blank/missing, progress,
feedback timing, idempotency/persistence, exact SQLite revision lookup, process lease,
interruption, provider/internal failures, canonical hashes and safe trace cleanup.
The grading UI has 12 Node event-flow checks; existing generation UI has 20.
The complete repository run passed **670 tests**, no failures or skips, with one
existing Starlette deprecation warning (107.90 s). Final verification details are
recorded in the handoff.

A real integrated Qwen smoke ran on 2026-11-20 using the exact installed
`qwen3:4b-q4_K_M`: job `G_705b5e794cab49a2a83962644c7c5aa2`, two synthetic questions,
COMPLETED 2/2, CORRECT / INCORRECT, zero uncertain/provider failures, 52.666 s command
wall time. Runtime evidence is under `data/runtime/grading_smoke/` and `grading.db`.
This is integration smoke evidence, not measured model accuracy or an SLA.

Inherited limitations remain: bounded arithmetic/normalization, Qwen-dependent
semantic diagnosis and skill attribution, broad evidence spans, known wrong-action
N07 and invalid-evidence P07 cases, and occasional English explanation leakage.
Canonical hashes are unchanged. Old post-extraction grading/demo code remains
isolated and is not semantically equivalent to this API. No original standalone
files were changed; no commit/push was performed.

References: [final Vietnamese design](../design/W08_AI_Grading_Design_Final.md),
[handoff](../report/W08_AI_Grading_Handoff.md),
[source manifest](grading_source_manifest.json),
[database audit](../report/w08_grading_database_audit.json).
