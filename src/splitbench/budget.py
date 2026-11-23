"""Budget enforcer: one cap on total tokens (input plus output, all agents) and one on tool calls.

Before a model call, the agent reserves its input tokens plus room for output. The
budget grants at most what is left, so `used + reserved` never passes the cap, even with
parallel workers. A call that cannot get one output token does not run.
"""

from __future__ import annotations

import math
import threading


def count_tokens(text: str) -> int:
    """Token count used for budgets: one token per 4 characters, rounded up."""
    return max(1, math.ceil(len(text) / 4))


class BudgetExhausted(Exception):
    pass


class Budget:
    def __init__(self, max_tokens: int, max_tool_calls: int, parent: Budget | None = None):
        self.max_tokens = max_tokens
        self.max_tool_calls = max_tool_calls
        self.parent = parent
        self.used_tokens = 0
        self.reserved = 0
        self.tool_calls = 0
        self.lock = threading.Lock() if parent is None else parent.lock

    # A child budget is a slice of its parent. Both caps hold at once.
    def child(self, max_tokens: int, max_tool_calls: int) -> Budget:
        return Budget(max_tokens, max_tool_calls, parent=self)

    def _chain(self):
        b = self
        while b is not None:
            yield b
            b = b.parent

    def tokens_left(self) -> int:
        with self.lock:
            return min(b.max_tokens - b.used_tokens - b.reserved for b in self._chain())

    def calls_left(self) -> int:
        with self.lock:
            return min(b.max_tool_calls - b.tool_calls for b in self._chain())

    def reserve(self, input_tokens: int, want_output: int) -> int:
        """Reserve room for one call. Returns the output tokens granted."""
        with self.lock:
            left = min(b.max_tokens - b.used_tokens - b.reserved for b in self._chain())
            grant = min(want_output, left - input_tokens)
            if grant < 1:
                raise BudgetExhausted("token cap reached")
            for b in self._chain():
                b.reserved += input_tokens + grant
            return grant

    def charge(self, reserved_input: int, granted: int, output_tokens: int) -> int:
        """Release a reservation and charge what the call used. Returns the tokens charged.

        Tokens are counted by `count_tokens` on the exact prompt and on the output text,
        which the agent cuts to the grant. So a charge never exceeds its reservation.
        """
        with self.lock:
            spent = reserved_input + min(output_tokens, granted)
            for b in self._chain():
                b.reserved -= reserved_input + granted
                b.used_tokens += spent
            return spent

    def use_tool(self) -> None:
        with self.lock:
            if any(b.tool_calls >= b.max_tool_calls for b in self._chain()):
                raise BudgetExhausted("tool-call cap reached")
            for b in self._chain():
                b.tool_calls += 1
