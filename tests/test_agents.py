import json

import pytest
from fakes import SpamModel
from helpers import CORPUS, TASKS, first

from splitbench import agents, metrics
from splitbench.budget import Budget
from splitbench.models import ScriptedModel

BIG = (10**7, 10**5)


def states(run):
    return [e["state"] for e in run.log.events if e["event"] == "state"]


@pytest.mark.parametrize("arch", list(agents.ARCHS))
def test_every_architecture_solves_every_dev_task_without_a_cap(arch):
    for t in [t for t in TASKS if t["split"] == "dev"]:
        run = agents.ARCHS[arch](t, ScriptedModel(), CORPUS, Budget(*BIG))
        assert metrics.correct(run.answer, t), (arch, t["id"], run.answer, t["answer"])


def test_orchestrator_walks_plan_dispatch_collect_combine_stop():
    run = agents.orchestrator(first(ttype="breadth"), ScriptedModel(), CORPUS, Budget(*BIG))
    assert states(run) == ["plan", "dispatch", "collect", "combine"]
    assert 3 <= len(run.upstream) <= 5
    assert run.final_agent.tools is False  # no tool calls after the plan


def test_orchestrator_sends_a_chain_to_one_worker():
    run = agents.orchestrator(first(ttype="depth"), ScriptedModel(), CORPUS, Budget(*BIG))
    assert states(run) == ["plan", "dispatch", "collect", "combine"] and len(run.upstream) == 1


class _Lead:
    name = "lead-fake"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, messages, max_output):
        return json.dumps(self.reply), {}


def test_plan_to_stop_when_the_lead_answers_at_once():
    run = agents.orchestrator(first(), _Lead({"answer": "42"}), CORPUS, Budget(*BIG))
    assert states(run) == ["plan"] and run.answer == "42" and run.upstream == []


def test_plan_to_stop_on_an_empty_plan():
    run = agents.orchestrator(first(), _Lead({"plan": []}), CORPUS, Budget(*BIG))
    assert states(run) == ["plan"] and run.answer is None


def test_collect_marks_a_worker_that_stopped_at_the_cap():
    """Broken case: a worker that hit its share of the budget is silently skipped, so the lead
    cannot tell missing facts from facts that do not exist."""
    run = agents.orchestrator(first(ttype="breadth"), SpamModel(pad=200), CORPUS, Budget(6000, 40))
    reports = [m["content"] for m in run.final_agent.history if m["content"].startswith("Worker reports:")]
    assert reports and reports[0].count("no report (stopped at the budget limit)") == 5
    run = agents.orchestrator(first(ttype="breadth"), ScriptedModel(), CORPUS, Budget(4500, 40))
    reports = [m["content"] for m in run.final_agent.history if m["content"].startswith("Worker reports:")]
    assert "empty report" in reports[0]


def test_workers_get_equal_shares_and_the_lead_keeps_a_reserve():
    budget = Budget(40_000, 40)
    run = agents.orchestrator(first(ttype="mixed"), ScriptedModel(), CORPUS, budget)
    shares = {w.budget.max_tokens for w in run.upstream}
    assert len(shares) == 1
    assert sum(w.budget.max_tokens for w in run.upstream) <= 40_000 * (1 - agents.COMBINE_SHARE)


def test_pipeline_hands_evidence_to_the_checker():
    run = agents.pipeline(first(ttype="depth"), ScriptedModel(), CORPUS, Budget(*BIG))
    roles = [a.role for a in run.all_agents]
    assert roles == ["planner", "executor", "checker"]
    assert "Evidence: " in run.final_agent.history[0]["content"]
    assert "(none)" not in run.final_agent.history[0]["content"]
    planner = run.all_agents[0]
    assert not any(e["event"] == "tool" and e["agent"] == "planner" for e in run.log.events)
    assert planner.result and "plan" in planner.result


def test_scratchpad_keeps_two_turns_and_the_pad():
    run = agents.scratchpad(first(ttype="breadth"), ScriptedModel(), CORPUS, Budget(*BIG))
    a = run.final_agent
    msgs = a.messages()
    assert len(msgs) <= 2 + 2 * agents.SCRATCH_KEEP
    assert "Scratchpad:" in msgs[1]["content"] and a.scratchpad


def test_same_base_prompt_and_tool_text_for_every_role():
    """Guard against prompts that favor one design: only the role line differs."""
    for role in agents.ROLES:
        a = agents.Agent("x", role, "Task: t", None, CORPUS, Budget(*BIG), agents.Log())
        assert a.system.startswith(agents.BASE) and a.system[len(agents.BASE) :] == agents.ROLES[role]


def test_threads_and_lockstep_agree_when_the_budget_is_loose():
    t = first(ttype="mixed")
    a = agents.orchestrator(t, ScriptedModel(), CORPUS, Budget(*BIG), parallel="threads")
    b = agents.orchestrator(t, ScriptedModel(), CORPUS, Budget(*BIG), parallel="lockstep")
    assert a.answer == b.answer == t["answer"]
