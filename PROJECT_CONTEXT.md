# Project context: splitbench

## What it is

splitbench tests when splitting work across several agents beats one agent, when every design gets the same token budget and the same tool-call budget. The tasks have exact answers, so no judge decides the score.

## Status

v0.1.0-rc1 on branch `claude/project-thread-mok4pw`. The full study ran with the scripted model. No free-model run happened, because the build machine had no provider key (see BLOCKERS.md).

## Stack

Python 3.11 or newer, the standard library only (threads for parallel workers), pytest and ruff for development. No agent framework.

## Commands

- `./init.sh`: venv, install, lint, link check, offline tests.
- `splitbench generate` and `splitbench check-frozen`: write and verify the corpus and the 60 tasks.
- `splitbench oracle`: solve every task with the tools and no model.
- `splitbench run`: the held-out study with the scripted model at both budgets.
- `splitbench run --provider groq --mode record`: record mode with a free model and a key.
- `splitbench report`, `splitbench readme --check`: write or check the generated README blocks.
- `splitbench probe`: check the record-mode hosts.

## Layout

- `src/splitbench/corpus.py`: seeded corpus generator and answer key.
- `src/splitbench/facts.py`: fact sentences and the parser.
- `src/splitbench/tasks.py`: the 60 tasks, the split and the freeze.
- `src/splitbench/procedures.py`: task templates and the procedures that answer them.
- `src/splitbench/tools.py`: BM25 `search` and `read_doc`.
- `src/splitbench/oracle.py`: oracle solver.
- `src/splitbench/budget.py`: the budget enforcer.
- `src/splitbench/models.py`: scripted model and the record/replay chat model.
- `src/splitbench/agents.py`: agent loop and the four architectures.
- `src/splitbench/metrics.py`: scoring, handoff loss, MAST tags, intervals.
- `src/splitbench/runner.py`: resumable study runner.
- `src/splitbench/report.py`: summary, report, README blocks and the static page.
- `data/`: frozen corpus and tasks. `results/`: run files, summaries, transcripts.

## Rules

- Tests run offline. `tests/conftest.py` blocks every non-local connection.
- Never change `data/` or the answer key to make code pass.
- Every architecture uses the same base prompt and tool text. Only the role line differs.
- Budget levels were set on dev tasks only. Do not tune on held-out tasks.
- README numbers live only between `<!-- splitbench:NAME -->` markers.

## Skills that fit

superpowers (plans, TDD, debugging, verification, code review), ponytail principles (least code), humanizer for docs.

## Do not read

`.venv/`, `results/transcripts/`, `results/cache/`, `docs/build/BUILD_PROMPT.md` unless you need the brief.
