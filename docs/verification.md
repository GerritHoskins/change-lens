# Independent Verification of Acceptance Criteria

Each acceptance criterion in `02-mvp-spec.md` §7 is checked by someone other than its author against the plan (`03`, `03a`, `04`, `05`). Checked by `scripts/check-verification.ps1`.

- **Verifier:** a named reviewer (agent name or person). It must not be the author.
- **Result:** `pass`, `fail` or `accepted-gap`. An accepted gap needs a reason in the evidence column and a decision-log entry.

| AC | Verifier | Method | Result | Evidence |
|---|---|---|---|---|
