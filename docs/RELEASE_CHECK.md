# Release check

Run on 2026-11-23 before v0.1.0-rc1.

| Step | Result |
| --- | --- |
| `gitleaks git -v .` over the whole history | no leaks found |
| `gitleaks git --pre-commit --redact --staged` before each commit | no leaks found |
| `pip-audit` on the project | no known vulnerabilities. The package has no runtime dependencies |
| `ruff check --select S src scripts` | two findings fixed (the chat model now checks its URL scheme, and the runner raises instead of using `assert`). Five kept, listed below |
| `actionlint` | clean |
| `scripts/check_links.py` | every relative link and anchor resolves. External links are listed as not checked, because the build machine cannot reach them |
| GitHub Actions on the branch | CI run 1 on commit 25a7fc1 passed |
| Review of the branch diff by a fresh subagent | see below |
| Outside check by a fresh subagent on a clean clone | see below |

Ruff findings kept on purpose:

- **S311 in `corpus.py`, `tasks.py` and `metrics.py`:** seeded `random.Random` builds the invented corpus and the bootstrap resamples. Nothing here needs a secure random source, and a seed makes the study repeatable.
- **S603 and S607 in `cli.py`:** `splitbench probe` runs `curl` with fixed arguments and a timeout. No user text reaches the command.

## Review of the branch diff

A fresh subagent reviewed `src`, `tests`, `scripts`, CI, `init.sh` and `pyproject.toml`. It confirmed that every model call reserves first, every tool call is counted, child budgets share the root lock, every role gets the same base prompt, the scripted model reads only its own messages, and replay never sends a request. It found four must-fix bugs. All four are fixed, each with a test that failed first:

1. **Worker errors were hidden in threads mode.** A worker that raised ended with no result, and the run looked like an ordinary orchestrator failure. `run_parallel` now re-raises the first error after the join. Test: `test_a_worker_error_in_threads_mode_is_raised_not_hidden`.
2. **Threads broke replay.** Each worker's prompt shows the shared budget left, which depends on thread timing, so a recorded prompt could hash differently on replay. The CLI now runs workers in lockstep for every model.
3. **A decimal point matched a whole number.** `correct("12.5")` matched the key `125`. Number answers now must be whole numbers after removing thousands separators. Test: `test_a_decimal_point_is_not_an_exact_match_for_a_whole_number`. No stored result changed, because every scripted answer is a whole number.
4. **A model name with a slash broke the result paths.** The OpenRouter default name holds `/`. The meta and summary paths now go through `runner.safe`. Test: `test_result_files_for_a_model_name_with_a_slash`.

Nice-to-have items also fixed: the runner writes and flushes the transcript before the run row, `load_runs` skips a line cut by a hard stop, the chat model caches only answers that hold choices and writes the cache file atomically, the decision guide skips a level with no single-agent runs, and the MAST rule text matches the code.

Not fixed: resume matches on task, design and level only. If someone changes `runner.BUDGETS`, old rows would mix with new ones. `DECISIONS.md` fixes the budgets, and a new budget level should use a new results file.

## Outside check

A fresh subagent cloned the repo into a clean folder, ran `./init.sh` and checked each Done-means item with its own commands. Items 1, 2, 3, 5, 6 and 7 passed. Item 4 is blocked, as the README says. It spot checked five README numbers against the summary file, confirmed that a second `splitbench run` leaves all 320 transcripts in place, and found no dash punctuation or semicolons in the README prose.

Its minor notes, and what I did:

- Half values rounded two ways because of float rounding. The report now rounds halves up with `report.one`.
- The badge and the clone command work for others only once the repo is public. That is in `docs/HUMAN_STEPS.md`.
- The Cowork prompt now tells Cowork not to ask questions and not to stop without a result.
