# ChangeLens verification
Read docs/SOP.md, the assigned item in docs/05-backlog.md (private, local only), its named ADRs, backend/README.md
and app/README.md only as relevant. Preserve traceability and independently verified evidence.
Do not reinterpret plan-check success as proof of the implemented product.
Use synthetic documents/labels. Real customer documents, labels and held-out data stay out
of Git, prompts and PR artifacts. Never reroll frozen evaluation samples or relax thresholds.
scripts/ci.ps1 checks tracked files only and force-reinstalls locked Python dependencies.
Do not call it an offline command. Run offline component checks with existing environments
first. A full CI run requires approved dependency-network/environment setup; validate newly
added files separately before staging. Do not stage user changes to satisfy the CI script.
Relevant commands to confirm in the current checkout:
- .venv/Scripts/python -m unittest discover -s scripts/eval
- backend/.venv/Scripts/python -m pytest backend/tests/unit -q -c backend/pytest.ini
- powershell -NoProfile -File scripts/check-trace.ps1
- powershell -NoProfile -File scripts/check-verification.ps1
- Flutter analyze/test in app/ with existing dependencies and network disabled.
Backend integration uses disposable Postgres/MinIO. Inspect compose volumes/destinations;
do not start/reset an existing data service without approval. Actual IONOS/model/Auth calls,
paid evaluations, push notification tests and physical iPhone/Android checks require approval.
Record findings using repo-owned review-ledger/verification conventions when in approved scope.
Do not replace accepted ADR decisions in place. Changes need the documented ADR procedure.
Publication target: GitHub GerritHoskins/change-lens. No deployment or external testers.
