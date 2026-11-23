# Contributing

Thanks for looking. This is a small project, so the rules are short.

1. Run `./init.sh` before and after a change. It installs the dev tools, runs ruff, checks links and runs the offline tests.
2. Write the test first. A new architecture needs a budget test in `tests/test_budget.py` and a correctness test with no cap in `tests/test_agents.py`.
3. Never type a number into the README. Rerun the study, then run `splitbench report`.
4. Never edit `data/` by hand. The corpus and tasks are frozen by `data/FROZEN.sha256`, and `splitbench check-frozen` must pass.
5. Give every architecture the same base prompt, the same tool text and the same budget. That is the point of the study.
6. Keep tests offline. `tests/conftest.py` fails any test that reaches a host other than localhost.
7. Keep secrets out of the repo. Run `gitleaks git --pre-commit --redact --staged --verbose` before you commit. Keys go in a local `.env`, which git ignores.
8. Write docs in plain words and active voice, with no em dashes and no semicolons in prose.
