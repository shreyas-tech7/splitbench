"""Measure dev-split token and tool-call use with no cap. Budget levels in runner.BUDGETS came from this."""

import statistics

from splitbench import agents
from splitbench import tasks as T
from splitbench.budget import Budget
from splitbench.models import ScriptedModel
from splitbench.tools import Corpus

docs, tasks = T.load()
c = Corpus(docs)
m = ScriptedModel()
toks, calls = [], []
for t in tasks:
    if t["split"] != "dev":
        continue
    for a in ["single", "orchestrator", "pipeline", "scratchpad"]:
        b = Budget(10**9, 10**6)
        agents.ARCHS[a](t, m, c, b, parallel="lockstep")
        toks.append(b.used_tokens)
        calls.append(b.tool_calls)
print("median tokens", statistics.median(toks), "median calls", statistics.median(calls))
print("max tokens", max(toks), "max calls", max(calls), "n", len(toks))
