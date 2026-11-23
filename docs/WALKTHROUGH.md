# Walkthrough

A tour of every file. Short sentences, one idea each.

## The idea

splitbench asks one question. Does a team of agents beat one agent when both get the same budget? Every design gets the same tokens, the same tool calls, the same base prompt and the same tools. The answer key is exact, so no judge model is needed.

## Data

- `data/corpus.jsonl` holds the invented documents. Each line is one document with an id, a title and text.
- `data/tasks.json` holds the tasks. Each task has a question, an exact answer, the facts it needs and its split.
- `data/FROZEN.sha256` is a digest of both files. `splitbench check-frozen` rebuilds them and compares.

## Source, in the order a run uses it

- `src/splitbench/facts.py` writes each fact as one sentence and reads it back. One parser serves documents, notes and reports.
- `src/splitbench/corpus.py` invents the companies and writes their documents. Each company has a profile, two annual filings, leadership news and product news. Sector directories and city registers list the members.
- `src/splitbench/procedures.py` holds the twelve task templates. Each template has a procedure that answers it from known facts. When a fact is missing, `next_action` says which tool call would find it.
- `src/splitbench/tasks.py` picks the tasks, rejects ties, gives each type a dev part and a held-out part, and freezes the files.
- `src/splitbench/oracle.py` solves every task with the tools and no model. It proves that each task is answerable.
- `src/splitbench/tools.py` has the two tools. `search` ranks titles and text with BM25 and returns ids and titles. `read_doc` returns one document.
- `src/splitbench/budget.py` enforces the caps. It reserves tokens before each call and cuts the output to the grant. A child budget gives a worker its slice of the same pool.
- `src/splitbench/models.py` has the scripted model and the chat model. The scripted model reads only its own prompt. The chat model calls an OpenAI style API in record mode and reads a cache in replay mode.
- `src/splitbench/agents.py` has the four designs. `Agent` runs one role. `orchestrator` is a state machine: plan, dispatch, collect, combine, stop. `pipeline` runs planner, executor and checker.
- `src/splitbench/metrics.py` scores answers, measures handoff loss, counts repeated calls and tags failures with a MAST group.
- `src/splitbench/runner.py` runs every design on every task at each budget. It appends each run to a file, so a stopped study resumes.
- `src/splitbench/report.py` turns result files into the summary, the report, the page and the README blocks.
- `src/splitbench/cli.py` is the `splitbench` command.

## Results

- `results/runs-scripted-v1-heldout.jsonl` has one line per run.
- `results/runs-scripted-v1-heldout-seed11.jsonl` is the same study on a corpus from another seed.
- `results/summary-scripted-v1-heldout.json` is what the README tables come from.
- `results/transcripts/` holds every prompt and output, gzipped.
- `results/oracle.json` and `results/probe.json` record the oracle run and the host check.

## Tests

- `tests/test_budget.py` proves that no design goes over a cap, with a model that tries to spend everything.
- `tests/test_agents.py` checks each orchestrator state and the pipeline handoff.
- `tests/test_record.py` checks record and replay against a local fake server, the backoff on rate limits, and resume.
- `tests/test_repo.py` checks the README order, the generated blocks and the writing rules.
- `tests/conftest.py` fails any test that opens a connection to a host that is not local.

## Docs

- `docs/REPORT.md` is the full generated report.
- `docs/index.html` is the same results as a page that opens from disk.
- `docs/DEMO.md` is a real terminal session.
- `docs/INTERVIEW_QA.md` answers the questions people ask about this project.
- `docs/HUMAN_STEPS.md` lists what only Shreyas can do.
