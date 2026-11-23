from helpers import CORPUS, first

from splitbench import agents, metrics
from splitbench.budget import Budget
from splitbench.models import ScriptedModel


def test_exact_match_rules():
    num = {"answer": "1234", "answer_kind": "number"}
    assert metrics.correct("$1,234 million", num) and metrics.correct("1234", num)
    assert not metrics.correct("1235", num) and not metrics.correct(None, num)
    lst = {"answer": "Varn Labs, Kest Group, Talo Works", "answer_kind": "list3"}
    assert metrics.correct("varn labs, kest group, talo works.", lst)
    assert not metrics.correct("Kest Group, Varn Labs, Talo Works", lst)  # order counts
    name = {"answer": "Ada Quill", "answer_kind": "name"}
    assert metrics.correct("Ada Quill.", name) and not metrics.correct("Ada", name)


def test_wilson_and_bootstrap():
    lo, hi = metrics.wilson(20, 40)
    assert 0.34 < lo < 0.36 and 0.64 < hi < 0.66
    assert metrics.wilson(0, 0) == (0.0, 0.0)
    lo, hi = metrics.bootstrap_mean([1.0] * 10)
    assert lo == hi == 1.0


def test_single_agent_has_no_handoff_loss():
    t = first(ttype="breadth")
    run = agents.single(t, ScriptedModel(), CORPUS, Budget(10**7, 1000))
    assert metrics.handoff(run, t) is None


def test_handoff_loss_counts_facts_a_worker_found_but_never_passed_on():
    """Broken case: loss measured on the worker's own context, so a lost report looks like zero loss."""
    t = first(ttype="breadth")
    run = agents.orchestrator(t, ScriptedModel(), CORPUS, Budget(10**7, 1000))
    clean = metrics.handoff(run, t)
    assert clean["found"] > 0 and clean["loss"] == 0.0 and clean["dropped"] == 0.0
    # Cut one worker's report after the fact, and rebuild the lead's view from the cut reports.
    w = run.upstream[0]
    w.result = {"report": ""}
    hist = run.final_agent.history
    i = next(i for i, m in enumerate(hist) if m["content"].startswith("Worker reports:"))
    hist[i] = {
        "role": "user",
        "content": "\n".join(x for x in hist[i]["content"].splitlines() if not x.startswith(f"{w.id}:")),
    }
    cut = metrics.handoff(run, t)
    assert cut["loss"] > 0 and cut["dropped"] > 0 and cut["found"] == clean["found"]


def test_mast_rules():
    t = {"answer": "12", "answer_kind": "number", "evidence": []}

    class R:
        answer = None
        log = agents.Log()

    r = R()
    assert metrics.mast_tag(r, t, True, None) is None
    assert metrics.mast_tag(r, t, False, {"found": 4, "reached": 2}) == "FC2"
    assert metrics.mast_tag(r, t, False, None) == "FC3"  # stopped with no answer, no repeats
    r.log.add(agent="a", event="tool", action={"tool": "search", "query": "q"})
    r.log.add(agent="a", event="tool", action={"tool": "search", "query": "q"})
    assert metrics.mast_tag(r, t, False, None) == "FC1"  # step repetition
    r.answer = "unknown"
    assert metrics.mast_tag(r, t, False, None) == "FC1"  # wrong form
    r.answer = "13"
    assert metrics.mast_tag(r, t, False, None) == "FC3"


def test_a_decimal_point_is_not_an_exact_match_for_a_whole_number():
    """Broken case: "12.5" matched the key "125" because the point became a space and spaces were dropped."""
    task = {"answer": "125", "answer_kind": "number"}
    assert not metrics.correct("12.5", task)
    assert not metrics.correct("1.25", task)
    assert metrics.correct("125", task) and metrics.correct(" 125 ", task)
    assert metrics.correct("1,250", {"answer": "1250", "answer_kind": "number"})
    assert metrics.correct("$1,250", {"answer": "1250", "answer_kind": "number"})
