Recorded synthetic P/N proposal responses from frozen v11 selected runs.
Only inference-allowed context, raw model responses, payload hashes and standalone compact expected outputs are retained.
No benchmark gold, scenario labels or annotations enter inference. Names are test-only identifiers.
Original source SHA-256: f5d2b37ff9bf2a807d0107946c473a68f397b19b335feae8c3c5bcfd76d0cc0c.
Generated on 2026-11-20 by replaying the verified standalone formatter, not by asserting AI accuracy.

`frozen_standalone_v11.py.txt` is the exact original `run_test.py`, copied only
after verifying the SHA-256 above against the supplied sibling source. It is
test-only provenance data, parsed with `ast` and never imported/executed. Its full
contents (including benchmark helpers) are retained solely so the raw source hash
can be verified; no benchmark evaluation code is added to application runtime.
`.gitattributes` disables newline conversion for this file to preserve raw bytes.

`tools/grading_provenance.py` parses this pinned reference and both integrated
modules under the current Python interpreter. The original 38 per-definition
hashes remain in the manifest as historical evidence: `ast.dump` default output
changed in Python 3.13, so those digests are not cross-version AST identities.
No expected values are computed from production code during tests. The reference
is repository-local, so CI/runtime need no sibling checkout. See
`docs/report/W08_Grading_Provenance_Repair.md` for the diagnosis and verification.
