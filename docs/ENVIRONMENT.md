# Build environment

Probes from the build machine on 2026-11-23. These explain why record mode did not run.

| Host | Result |
| --- | --- |
| api.groq.com | refused by the network proxy (403) |
| openrouter.ai | refused by the network proxy (403) |
| generativelanguage.googleapis.com | reachable, but a request with no key returns 403 PERMISSION_DENIED |
| huggingface.co, api.osv.dev, semgrep.dev | refused by the network proxy (403) |
| pypi.org and registry.npmjs.org for `splitbench` | 404, so the name was free |
| raw.githubusercontent.com for cheahjs/free-llm-api-resources | 404 on the README path tried |

No provider key was set in the environment, so no model request was sent. `splitbench probe` repeats the host check and writes `results/probe.json`.

The machine: Intel Xeon Processor @ 2.30GHz, 4 cores, Python 3.11.18 in the project venv.
