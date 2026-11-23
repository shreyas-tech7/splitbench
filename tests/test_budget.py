import threading

import pytest
from fakes import FixedModel, SpamModel
from helpers import CORPUS, first

from splitbench import agents
from splitbench.budget import Budget, BudgetExhausted
from splitbench.models import ScriptedModel

CAPS = [(300, 2), (1500, 5), (6000, 12), (20000, 40)]


@pytest.mark.parametrize("arch", list(agents.ARCHS))
@pytest.mark.parametrize("cap", CAPS)
@pytest.mark.parametrize("parallel", ["lockstep", "threads"])
def test_no_architecture_can_pass_either_cap(arch, cap, parallel):
    """Broken case: a check after the call instead of a reservation before it lets the last call,
    or parallel workers together, go over the cap."""
    budget = Budget(*cap)
    run = agents.ARCHS[arch](first(ttype="breadth"), SpamModel(), CORPUS, budget, parallel=parallel)
    assert budget.used_tokens <= cap[0]
    assert budget.tool_calls <= cap[1]
    assert budget.reserved == 0
    assert run.answer is None


@pytest.mark.parametrize("arch", list(agents.ARCHS))
@pytest.mark.parametrize("ttype", ["breadth", "depth", "mixed"])
def test_scripted_runs_stay_under_tight_caps(arch, ttype):
    for cap in [(2000, 3), (5000, 8), (9000, 15)]:
        budget = Budget(*cap)
        agents.ARCHS[arch](first(ttype=ttype), ScriptedModel(), CORPUS, budget)
        assert budget.used_tokens <= cap[0] and budget.tool_calls <= cap[1]


def test_charged_tokens_equal_the_known_counts():
    """Broken case: tokens counted on the wrong text, or the output charged twice."""
    model = FixedModel(n=10)
    budget = Budget(10_000, 10)
    run = agents.single(first(), model, CORPUS, budget)
    assert run.answer is not None
    assert budget.used_tokens == sum(model.seen) + 10 * len(model.seen)


def test_reservations_are_atomic_across_threads():
    budget = Budget(1000, 1000)
    granted = []

    def take():
        try:
            granted.append(budget.reserve(50, 100))
        except BudgetExhausted:
            pass

    ts = [threading.Thread(target=take) for _ in range(50)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sum(granted) + 50 * len(granted) <= 1000


def test_child_budget_holds_both_caps():
    parent = Budget(1000, 10)
    child = parent.child(400, 3)
    assert child.reserve(100, 500) == 300
    with pytest.raises(BudgetExhausted):
        child.reserve(10, 10)
    child.charge(100, 300, 20)
    assert parent.used_tokens == 120 and parent.reserved == 0
    for _ in range(3):
        child.use_tool()
    with pytest.raises(BudgetExhausted):
        child.use_tool()
    assert parent.tool_calls == 3
