# Blockers

| Date | What failed | Exact error | What I did instead |
| --- | --- | --- | --- |
| 2026-11-23 | Record-mode hosts | `curl: (56) CONNECT tunnel failed, response 403` for api.groq.com and openrouter.ai. No `GROQ_API_KEY` or `OPENROUTER_API_KEY` set. generativelanguage.googleapis.com answers, but a request without a key returns `403 PERMISSION_DENIED` | Built record and replay against a local fake OpenAI server in tests. Ran the full study with the scripted model and labeled every number as scripted. Manual step in `docs/HUMAN_STEPS.md` |
| 2026-11-23 | Skill installs | `npx -y skills add DietrichGebert/ponytail -g -a claude-code -y` was denied by the permission system | Used the superpowers skills already in the session. Followed ponytail rules by hand. Reviews ran as fresh subagents |
| 2026-11-23 | PR, tag, About and topics from this VM | The proxy refuses `gh pr`, tag pushes and GraphQL (per the session brief) | The coordinator opens the PR and sets About and topics. Values are in `docs/GITHUB_ABOUT.md` and `docs/topics.txt` |
| 2026-11-23 | huggingface.co, api.osv.dev, semgrep.dev | `CONNECT tunnel failed, response 403` | No embedding model is needed. pip-audit and `ruff --select S` replace osv-scanner and semgrep |
| 2026-11-23 | Live bug, score 5x5=25, fixed | The lead's own plan quoted "The Robotics companies are: ..." for each worker group, so the parser replaced the full member list with the last group, and the orchestrator failed every mixed task with no cap | Worker hints now say "Document ids: ...", and the parser reads document ids from any text but members only from the directory sentence. `test_every_architecture_solves_every_dev_task_without_a_cap` covers it |
