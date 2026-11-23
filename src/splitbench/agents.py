"""The agent loop and the four architectures, in plain Python.

Every agent gets the same base instructions and the same tool descriptions. Only the
role line differs. Every prompt and every reply is logged.
"""

from __future__ import annotations

import json
import re
import threading
import time

from .budget import Budget, BudgetExhausted, count_tokens
from .tools import TOOL_TEXT, Corpus

MAX_OUTPUT = 512  # output cap per call, the same for every role
MAX_STEPS = 80  # a guard against loops; the budget normally stops a run first
SCRATCH_KEEP = 2  # the scratchpad agent keeps only its last 2 turns in context

BASE = (
    "You are one agent in a research system over a corpus of short documents about invented companies.\n"
    f"{TOOL_TEXT}\n"
    "Reply with exactly one JSON object and nothing else. When you report facts, quote the fact "
    "sentences exactly as the documents write them. Every agent shares one budget of tokens and tool "
    "calls. Each prompt ends with what is left.\n"
)
ROLES = {
    "single": 'Your role: single. Solve the task with the tools. Then reply {"answer": "<final answer>"}.',
    "scratch": (
        'Your role: scratch. Solve the task with the tools. Then reply {"answer": "<final answer>"}. '
        'You may add "note": "<text>" to any reply. Notes go to a scratchpad that every prompt shows. '
        f"Only your last {SCRATCH_KEEP} turns stay in your context."
    ),
    "lead": (
        "Your role: lead. You may call tools to plan. Then reply "
        '{"plan": ["<subtask>", ...]} with 1 to 5 subtasks. Each worker gets one subtask, its own '
        'context and a share of the budget. After the workers report, reply {"answer": "<final answer>"}. '
        "You cannot call tools after the plan."
    ),
    "worker": 'Your role: worker. Do your subtask with the tools. Then reply {"report": "<fact sentences>"}.',
    "planner": 'Your role: planner. Write a plan for the task. Do not call tools. Reply {"plan": "<steps>"}.',
    "executor": (
        "Your role: executor. Follow the plan with the tools. Then reply "
        '{"answer": "<final answer>", "evidence": "<the fact sentences you used>"}.'
    ),
    "checker": (
        "Your role: checker. Check the executor's answer against its evidence. Call tools if a fact is "
        'missing or doubtful. Then reply {"answer": "<final answer>"}.'
    ),
}
TERMINAL = ("answer", "report", "plan")
JSON_RX = re.compile(r"\{.*\}", re.S)


def parse_action(text: str) -> dict | None:
    m = JSON_RX.search(text)
    if m:
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def cut(text: str, tokens: int) -> str:
    """Cut output text to `tokens`, the way a provider's max_tokens cuts it."""
    return text if count_tokens(text) <= tokens else text[: tokens * 4]


class Log:
    """Every model call and tool call of one run, in order. Thread safe."""

    def __init__(self):
        self.events: list[dict] = []
        self.lock = threading.Lock()

    def add(self, **event):
        with self.lock:
            event["seq"] = len(self.events)
            self.events.append(event)


class Agent:
    def __init__(
        self, agent_id, role, user_text, model, corpus: Corpus, budget: Budget, log: Log, tools: bool = True
    ):
        self.id, self.role, self.model, self.corpus = agent_id, role, model, corpus
        self.budget, self.log, self.tools = budget, log, tools
        self.system = BASE + ROLES[role]
        self.history: list[dict] = [{"role": "user", "content": user_text}]
        self.scratchpad: list[str] = []
        self.result: dict | None = None
        self.stopped: str | None = None
        self.steps = 0
        self.calls = 0  # model calls on this agent

    @property
    def done(self) -> bool:
        return self.result is not None or self.stopped is not None

    def messages(self) -> list[dict]:
        hist = [dict(m) for m in self.history]
        if self.role == "scratch":
            # Older turns leave the context. The scratchpad carries what the agent chose to keep.
            dropped = len(hist) - 1 - 2 * SCRATCH_KEEP
            if dropped > 0:
                hist = [hist[0], *hist[1 + dropped :]]
            pad = "\n".join(self.scratchpad) or "(empty)"
            hist[0] = {"role": "user", "content": f"{hist[0]['content']}\nScratchpad:\n{pad}"}
        line = f"Budget left: {self.budget.tokens_left()} tokens, {self.budget.calls_left()} tool calls."
        hist[-1] = {"role": hist[-1]["role"], "content": f"{hist[-1]['content']}\n{line}"}
        return [{"role": "system", "content": self.system}, *hist]

    def context_text(self) -> str:
        """Everything this agent can see now (for handoff-loss accounting)."""
        return "\n".join(m["content"] for m in self.messages()[1:])

    def step(self) -> None:
        if self.done:
            return
        if self.steps >= MAX_STEPS:
            self.stopped = "max_steps"
            return
        self.steps += 1
        msgs = self.messages()
        n_in = sum(count_tokens(m["content"]) for m in msgs)
        try:
            grant = self.budget.reserve(n_in, MAX_OUTPUT)
        except BudgetExhausted as e:
            self.stopped = "budget"
            self.log.add(agent=self.id, role=self.role, event="stop", reason=str(e))
            return
        t0 = time.perf_counter()
        try:
            text, usage = self.model.complete(msgs, grant)
        except Exception:
            self.budget.charge(n_in, grant, 0)
            raise
        text = cut(text, grant)
        spent = self.budget.charge(n_in, grant, count_tokens(text))
        self.calls += 1
        self.log.add(
            agent=self.id,
            role=self.role,
            event="model",
            prompt=msgs,
            output=text,
            input_tokens=n_in,
            output_tokens=spent - n_in,
            grant=grant,
            provider_usage=usage,
            seconds=round(time.perf_counter() - t0, 4),
        )
        self.history.append({"role": "assistant", "content": text})
        action = parse_action(text)
        if action is None:
            if self.role == "worker":  # a cut report still carries the sentences before the cut
                self.result = {"report": text}
                return
            self.history.append({"role": "user", "content": "Your reply was not one JSON object. Try again."})
            return
        if action.get("note") and self.role == "scratch":
            self.scratchpad.append(str(action["note"]))
        for key in TERMINAL:
            if key in action:
                self.result = action
                return
        if not self.tools or "tool" not in action:
            self.history.append({"role": "user", "content": "That action is not allowed for your role."})
            return
        try:
            self.budget.use_tool()
        except BudgetExhausted as e:
            self.stopped = "budget"
            self.log.add(agent=self.id, role=self.role, event="stop", reason=str(e))
            return
        result = self.corpus.call(action)
        self.log.add(agent=self.id, role=self.role, event="tool", action=action, result=result)
        self.history.append({"role": "user", "content": f"Tool result:\n{result}"})

    def run(self) -> Agent:
        while not self.done:
            self.step()
        return self


def run_parallel(agents: list[Agent], mode: str) -> None:
    """Run workers side by side. "lockstep" takes one step of each in turn, so a scripted run
    is deterministic. "threads" runs each worker in its own thread, for real models."""
    if mode == "threads":
        errors: list[BaseException] = []

        def target(a):
            try:
                a.run()
            except BaseException as e:  # re-raised below, so a provider error never looks like a result
                errors.append(e)

        ts = [threading.Thread(target=target, args=(a,)) for a in agents]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        if errors:
            raise errors[0]
        return
    while not all(a.done for a in agents):
        for a in agents:
            a.step()


class Run:
    """The outcome of one architecture on one task."""

    def __init__(self, arch, answer, log, budget, final_agent, upstream, critical_calls, seconds, stopped):
        self.arch, self.answer, self.log, self.budget = arch, answer, log, budget
        self.final_agent, self.upstream = final_agent, upstream
        self.critical_calls, self.seconds, self.stopped = critical_calls, seconds, stopped


def single(task, model, corpus, budget, parallel="lockstep", role="single") -> Run:
    log, t0 = Log(), time.perf_counter()
    a = Agent("single", role, f"Task: {task['question']}", model, corpus, budget, log).run()
    answer = (a.result or {}).get("answer")
    run = Run(role, answer, log, budget, a, [], a.calls, time.perf_counter() - t0, a.stopped)
    run.all_agents = [a]
    return run


def scratchpad(task, model, corpus, budget, parallel="lockstep") -> Run:
    return single(task, model, corpus, budget, parallel, role="scratch")


COMBINE_SHARE = 0.2  # share of the budget the lead keeps for its final call


def orchestrator(task, model, corpus, budget, parallel="lockstep") -> Run:
    """A state machine: plan, dispatch, collect, combine, stop."""
    log, t0 = Log(), time.perf_counter()
    lead = Agent("lead", "lead", f"Task: {task['question']}", model, corpus, budget, log)
    state, workers = "plan", []
    while state != "stop":
        log.add(agent="lead", role="lead", event="state", state=state)
        if state == "plan":
            lead.run()
            plan = (lead.result or {}).get("plan")
            if lead.result and "answer" in lead.result and plan is None:
                state = "stop"  # the lead answered without a plan
            elif not plan:
                state = "stop"
            else:
                state = "dispatch"
        elif state == "dispatch":
            subtasks = [str(s) for s in (plan if isinstance(plan, list) else [plan])][:5]
            share_t = int(budget.tokens_left() * (1 - COMBINE_SHARE)) // len(subtasks)
            share_c = max(1, budget.calls_left() // len(subtasks))
            workers = [
                Agent(
                    f"worker{i + 1}",
                    "worker",
                    f"Subtask: {s}",
                    model,
                    corpus,
                    budget.child(share_t, share_c),
                    log,
                )
                for i, s in enumerate(subtasks)
            ]
            run_parallel(workers, parallel)
            state = "collect"
        elif state == "collect":
            lines = []
            for w in workers:
                rep = (w.result or {}).get("report")
                if w.stopped:
                    lines.append(f"{w.id}: no report (stopped at the {w.stopped} limit)")
                else:
                    lines.append(f"{w.id}: {rep}" if rep else f"{w.id}: empty report")
            lead.history.append({"role": "user", "content": "Worker reports:\n" + "\n".join(lines)})
            lead.result = None
            lead.tools = False
            state = "combine"
        elif state == "combine":
            lead.run()
            state = "stop"
    answer = (lead.result or {}).get("answer")
    critical = lead.calls + max((w.calls for w in workers), default=0)
    run = Run(
        "orchestrator", answer, log, budget, lead, workers, critical, time.perf_counter() - t0, lead.stopped
    )
    run.all_agents = [lead, *workers]
    return run


EXECUTOR_SHARE = 0.65  # share of the budget after planning that the executor may use


def pipeline(task, model, corpus, budget, parallel="lockstep") -> Run:
    log, t0 = Log(), time.perf_counter()
    q = f"Task: {task['question']}"
    planner = Agent("planner", "planner", q, model, corpus, budget, log, tools=False).run()
    plan = str((planner.result or {}).get("plan", "")) or "(no plan)"
    ex_budget = budget.child(
        int(budget.tokens_left() * EXECUTOR_SHARE), max(1, int(budget.calls_left() * EXECUTOR_SHARE))
    )
    executor = Agent("executor", "executor", f"{q}\nPlan: {plan}", model, corpus, ex_budget, log).run()
    ex = executor.result or {}
    checker = Agent(
        "checker",
        "checker",
        f"{q}\nExecutor answer: {ex.get('answer', '(none)')}\nEvidence: {ex.get('evidence', '(none)')}",
        model,
        corpus,
        budget,
        log,
    ).run()
    answer = (checker.result or {}).get("answer")
    critical = planner.calls + executor.calls + checker.calls
    run = Run(
        "pipeline",
        answer,
        log,
        budget,
        checker,
        [executor],
        critical,
        time.perf_counter() - t0,
        checker.stopped,
    )
    run.all_agents = [planner, executor, checker]
    return run


ARCHS = {"single": single, "orchestrator": orchestrator, "pipeline": pipeline, "scratchpad": scratchpad}
