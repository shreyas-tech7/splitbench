# Progress

## 2026-11-23

- Done: corpus (301 documents), 60 frozen tasks, oracle 60 of 60, tools, budget enforcer with reservations, scripted model, four architectures, metrics, record and replay with a local fake server, runner, report generator, CLI. 87 tests pass, ruff clean.
- Budget levels set on dev with `scripts/dev_budget_stats.py`.
- Record mode blocked: no key, and groq and openrouter refused by the proxy. See BLOCKERS.md.
- Done: held-out study at both budgets, second-seed check (seed 11), generated report, README, CI, docs, demo, page, social preview. Fixed a bug that lost transcripts on a resumed run.
- Done: release check. Scans clean, CI green, four review bugs fixed with tests, outside check passed every item but the blocked free-model run.
- Done: release commit 51acbe0fc9c91bcaac662e9d28bbb11d0e9e69fa, written in CHANGELOG.md and docs/HUMAN_STEPS.md. Bundle and final report written.
- Open: a free-model record run, which needs a key (docs/HUMAN_STEPS.md step 7).
