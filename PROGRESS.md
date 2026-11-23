# Progress

## 2026-11-23

- Done: corpus (301 documents), 60 frozen tasks, oracle 60 of 60, tools, budget enforcer with reservations, scripted model, four architectures, metrics, record and replay with a local fake server, runner, report generator, CLI. 87 tests pass, ruff clean.
- Budget levels set on dev with `scripts/dev_budget_stats.py`.
- Record mode blocked: no key, and groq and openrouter refused by the proxy. See BLOCKERS.md.
- Done: held-out study at both budgets, second-seed check (seed 11), generated report, README, CI, docs, demo, page, social preview. Fixed a bug that lost transcripts on a resumed run.
- Next: release check (review subagent, scans, outside check), then the release SHA, bundle and hand-off.
