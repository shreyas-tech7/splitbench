import json

from helpers import CORPUS, first

from splitbench import agents
from splitbench.budget import Budget
from splitbench.models import ScriptedModel


def _msgs(role, user, *extra):
    return [
        {"role": "system", "content": agents.BASE + agents.ROLES[role]},
        {"role": "user", "content": user},
        *extra,
    ]


def test_it_reads_only_its_messages():
    """Broken case: the scripted model peeks at the answer key or a global cache."""
    t = first(ttype="breadth")
    m = ScriptedModel()
    a, _ = m.complete(_msgs("single", f"Task: {t['question']}"), 512)
    assert json.loads(a)["tool"] == "search"
    reg = CORPUS.search(json.loads(a)["query"])
    b, _ = m.complete(
        _msgs(
            "single",
            f"Task: {t['question']}",
            {"role": "assistant", "content": a},
            {"role": "user", "content": f"Tool result:\n{reg}"},
        ),
        512,
    )
    assert json.loads(b)["tool"] == "read_doc"


def test_it_answers_with_what_it_has_when_the_budget_line_is_low():
    t = first(ttype="breadth")
    text, _ = ScriptedModel().complete(
        _msgs("single", f"Task: {t['question']}\nBudget left: 50 tokens, 9 tool calls."), 512
    )
    assert "answer" in json.loads(text)


def test_worker_reports_quoted_fact_sentences():
    t = first(ttype="depth")
    run = agents.orchestrator(t, ScriptedModel(), CORPUS, Budget(10**7, 1000))
    report = run.upstream[0].result["report"]
    assert "The key supplier of" in report


def test_scripted_runs_are_deterministic():
    t = first(ttype="mixed")
    out = [agents.orchestrator(t, ScriptedModel(), CORPUS, Budget(9000, 20)) for _ in range(2)]
    assert out[0].answer == out[1].answer and out[0].budget.used_tokens == out[1].budget.used_tokens
