# Handover

Read PROJECT_CONTEXT.md first, then this file.

- **State:** v0.1.0-rc1 is complete except the free-model run. Release commit 51acbe0fc9c91bcaac662e9d28bbb11d0e9e69fa.
- **Branch:** `claude/project-thread-mok4pw`. Never push to main.
- **Done:** corpus, tasks, oracle, tools, budget, four designs, metrics, record and replay, held-out study at two budgets, second seed, README, CI, docs, release check.
- **Open:** a record run with a free model. It needs a key. Commands are in `docs/HUMAN_STEPS.md` step 7.
- **Open decision:** whether to add the hybrid design in `docs/PROPOSALS.md`.
- **Commands:** `./init.sh`, `.venv/bin/splitbench run`, `.venv/bin/splitbench report`, `.venv/bin/splitbench readme --check`.
- Never type numbers into the README. Run `splitbench report`.
