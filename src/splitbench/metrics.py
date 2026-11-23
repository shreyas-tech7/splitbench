"""Scoring, handoff loss, MAST failure tags and intervals."""

from __future__ import annotations

import math
import random
import re

from . import facts as F

PUNCT = re.compile(r"[^\w\s,]")


def norm(s) -> str:
    s = str(s or "").lower().replace("$", "").replace("million", "").replace("dollars", "")
    s = PUNCT.sub(" ", s.replace(",", " , "))
    return " ".join(s.split()).strip(" ,")


def items(s) -> list[str]:
    return [p.strip() for p in norm(s).split(",") if p.strip()]


def _whole(s):
    """A whole number from an answer like "1,250", "$1,250" or "1250 million". None otherwise."""
    t = str(s).strip().lower().replace("$", "").replace("million", "").replace("dollars", "").strip()
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    return int(t) if re.fullmatch(r"\d+", t) else None


def correct(answer, task) -> bool:
    """Exact match after light normalization. List answers must match item by item, in order."""
    if answer is None:
        return False
    if task["answer_kind"] == "list3":
        return items(answer) == items(task["answer"])
    if task["answer_kind"] == "number":
        return _whole(answer) is not None and _whole(answer) == _whole(task["answer"])
    return norm(answer) == norm(task["answer"])


def well_formed(answer, task) -> bool:
    if answer is None or norm(answer) in ("", "unknown"):
        return False
    if task["answer_kind"] == "list3":
        return len(items(answer)) == 3
    if task["answer_kind"] == "number":
        return re.fullmatch(r"\d+", norm(answer).replace(" ", "").replace(",", "")) is not None
    return True


def needed(task) -> set:
    """Facts the answer depends on, minus the lists that only say who is in a sector or city."""
    return {tuple(e) for e in task["evidence"] if e[0] not in ("sector_members", "city_members")}


def facts_in(text: str, want: set) -> set:
    kb = F.parse(text)
    return {k for k in want if k in kb}


def handoff(run, task) -> dict | None:
    """Handoff loss for a multi-agent run.

    found: needed facts that appeared in a tool result of an upstream agent (a worker, or the executor).
    reached: of those, the ones in the final agent's context when it answered.
    dropped: of those, the ones missing from the upstream agents' handoff messages
    (reports or evidence), even if the final agent found them again by itself.
    """
    if not run.upstream:
        return None
    want = needed(task)
    ups = {a.id for a in run.upstream}
    tool_text = "\n".join(e["result"] for e in run.log.events if e["event"] == "tool" and e["agent"] in ups)
    found = facts_in(tool_text, want)
    handed = "\n".join(
        str(v) for a in run.upstream for k, v in (a.result or {}).items() if k in ("report", "evidence")
    )
    reached = found & facts_in(run.final_agent.context_text(), want)
    sent = found & facts_in(handed, want)
    n = len(found)
    return {
        "found": n,
        "reached": len(reached),
        "loss": (n - len(reached)) / n if n else 0.0,
        "dropped": (n - len(sent)) / n if n else 0.0,
    }


def repeats(run) -> int:
    """Tool calls that repeat an earlier identical call by the same agent."""
    seen, n = set(), 0
    for e in run.log.events:
        if e["event"] == "tool":
            key = (e["agent"], str(sorted(e["action"].items())))
            n += key in seen
            seen.add(key)
    return n


MAST = {
    "FC1": "specification and system design",
    "FC2": "inter-agent misalignment",
    "FC3": "task verification and termination",
}


def mast_tag(run, task, ok: bool, hand: dict | None) -> str | None:
    """Tag a failed run with one MAST group, by fixed rules applied in this order.

    1. A multi-agent run that lost facts in a handoff: FC2 (information withholding).
    2. A run that stopped with no answer and repeated a tool call: FC1 (step repetition).
    3. A run that stopped with no answer: FC3 (premature termination).
    4. An answer in the wrong form: FC1 (disobeyed the task specification).
    5. A wrong answer while every needed fact was in the final context: FC3 (incorrect verification).
    6. Any other wrong answer, with needed facts never found: FC3 (incomplete verification).
    """
    if ok:
        return None
    if hand and hand["found"] and hand["reached"] < hand["found"]:
        return "FC2"
    if run.answer is None:
        return "FC1" if repeats(run) else "FC3"
    if not well_formed(run.answer, task):
        return "FC1"
    return "FC3"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def bootstrap_mean(xs: list[float], seed: int = 0, reps: int = 2000) -> tuple[float, float]:
    """95% percentile interval of the mean, resampling tasks."""
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(reps))
    return (means[int(0.025 * reps)], means[int(0.975 * reps) - 1])
