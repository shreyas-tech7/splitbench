"""Fake models with known token counts, for budget and protocol tests."""

import json

from splitbench.budget import count_tokens
from splitbench.models import ROLE_RX


class SpamModel:
    """Never answers. Leads plan five workers. Everyone else calls a tool with a long query,
    so outputs press against the output cap and tool calls press against the call cap."""

    name = "spam"

    def __init__(self, pad=3000):
        self.pad = pad
        self.calls = 0

    def complete(self, messages, max_output):
        self.calls += 1
        role = ROLE_RX.search(messages[0]["content"]).group(1)
        if role == "lead" and "Worker reports:" not in messages[-1]["content"]:
            text = json.dumps({"plan": [f"subtask {i}" for i in range(5)]})
        elif role == "planner":
            text = json.dumps({"plan": "x" * self.pad})
        else:
            text = json.dumps({"tool": "search", "query": "fiscal " * (self.pad // 7)})
        return text, {
            "input_tokens": sum(count_tokens(m["content"]) for m in messages),
            "output_tokens": count_tokens(text),
        }


class FixedModel:
    """Answers at once with a reply of exactly `n` tokens."""

    name = "fixed"

    def __init__(self, n=10):
        self.text = json.dumps({"answer": "x" * (4 * n - 14)})
        assert count_tokens(self.text) == n
        self.seen = []

    def complete(self, messages, max_output):
        self.seen.append(sum(count_tokens(m["content"]) for m in messages))
        return self.text, {"input_tokens": self.seen[-1], "output_tokens": count_tokens(self.text)}
