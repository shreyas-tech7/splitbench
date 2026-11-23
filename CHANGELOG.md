# Changelog

## v0.1.0-rc1 (2026-11-23)

Release commit: 51acbe0fc9c91bcaac662e9d28bbb11d0e9e69fa

- A corpus generator with an answer key, and 60 frozen tasks in three shapes, split into dev and held out.
- An oracle solver that answers every task with the tools and no model.
- Two tools, `search` and `read_doc`, and a budget enforcer that reserves before each call.
- Four designs: single agent, orchestrator with workers, planner executor checker pipeline, single agent with scratchpad.
- A deterministic scripted model, and a chat model with record and replay for free OpenAI style providers.
- Metrics: exact match, Wilson intervals, paired bootstrap, handoff loss, critical-path calls and MAST tags.
- A resumable runner, a second-seed check, a generated report, README blocks and a static results page.
- No free-model run yet, because the build machine had no key and its proxy refused the providers.
