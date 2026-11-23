"""Oracle solver: answers every task with the real tools and a text parser, no model.

It shows that each answer key value can be recovered from the corpus text alone.
"""

from __future__ import annotations

from . import facts as F
from . import procedures as P
from .tools import Corpus


def solve(task: dict, corpus: Corpus, max_calls: int = 200) -> tuple[str, int]:
    """Return (answer, tool calls used)."""
    known: dict = {}
    for calls in range(max_calls + 1):
        try:
            return P.solve(task["kind"], task["params"], P.KB(known)), calls
        except P.Missing as m:
            action = P.next_action(m.key, known)
            known.update(F.parse(corpus.call(action)))
    raise RuntimeError(f"oracle did not finish {task['id']} in {max_calls} calls")
