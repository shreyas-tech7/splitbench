# Plan

1. Corpus and tasks: 301 synthetic documents, 60 tasks (20 breadth, 20 depth, 20 mixed), dev and held-out split, frozen digest.
2. Oracle: solve every task with the tools and no model, to prove the tasks are answerable.
3. Tools and budget: BM25 search, read by id, and a budget enforcer that reserves before each call.
4. Scripted model: a deterministic model that only reasons over what is in its own context.
5. Architectures: single agent, orchestrator with workers, planner executor checker pipeline, single agent with scratchpad. All share one base prompt and one budget.
6. Metrics: success with Wilson intervals, tokens, tool calls, critical-path calls, handoff loss, MAST groups, paired bootstrap against single.
7. Record and replay for free models, tested against a local fake server.
8. Study: budgets set on dev, then the held-out run at both levels, then the generated README and report.
9. Docs, CI, release check, hand-off.
