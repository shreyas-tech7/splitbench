"""Models. `ScriptedModel` follows each role's protocol offline. `ChatModel` calls a free
OpenAI-compatible provider in record mode and replays the cached answers byte for byte.

Every model returns plain text that holds one JSON action. That works the same way on any
model, including free models whose tool calling is unreliable.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import facts as F
from . import procedures as P
from .budget import count_tokens

ROLE_RX = re.compile(r"Your role: (\w+)")
BUDGET_RX = re.compile(r"Budget left: (\d+) tokens, (\d+) tool calls")


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


class ScriptedModel:
    """A deterministic stand-in for an LLM.

    It reads only the messages it is given. It parses the task, collects the facts that
    are visible in its context, and asks for the next fact it lacks. When the budget line
    says the next step may not fit, it answers with what it has. It reasons perfectly
    over what it can see, so every difference between architectures comes from what
    reaches each agent's context and from what each protocol costs in tokens.
    """

    name = "scripted-v1"

    def complete(self, messages: list[dict], max_output: int) -> tuple[str, dict]:
        system = messages[0]["content"]
        role = ROLE_RX.search(system).group(1)
        task_text = messages[1]["content"]
        visible = "\n".join(m["content"] for m in messages[1:])
        known = F.parse(visible)
        m = BUDGET_RX.search(messages[-1]["content"])
        tokens_left, calls_left = (int(m.group(1)), int(m.group(2))) if m else (10**9, 10**9)
        prompt = sum(count_tokens(x["content"]) for x in messages)
        # The next round costs about this prompt again plus a tool result. Below that, stop and answer.
        low = tokens_left < 2 * prompt + 300 or calls_left < 1
        fn = getattr(self, f"_{role}")
        text = (
            fn(task_text, visible, known, low, messages, max_output)
            if role == "lead"
            else fn(task_text, visible, known, low, messages)
        )
        return text, {"input_tokens": prompt, "output_tokens": count_tokens(text)}

    # --- roles that solve a question with tools ---------------------------------------
    def _solve(self, question_text, known, low):
        q = P.parse_question(question_text)
        if q is None:
            return {"answer": "unknown"}, []
        kind, params = q
        kb = P.KB(known)
        try:
            return {"answer": P.solve(kind, params, kb)}, kb.used
        except P.Missing as miss:
            if low:
                kb = P.KB(known, lenient=True)
                return {"answer": P.solve(kind, params, kb)}, kb.used
            return P.next_action(miss.key, known), None

    def _single(self, task_text, visible, known, low, messages):
        action, _ = self._solve(task_text, known, low)
        return _dump(action)

    def _scratch(self, task_text, visible, known, low, messages):
        action, _ = self._solve(task_text, known, low)
        last = messages[-1]["content"]
        if last.startswith("Tool result:"):
            note = " ".join(F.fact_lines(last))
            if note:
                action["note"] = note
        return _dump(action)

    def _executor(self, task_text, visible, known, low, messages):
        action, used = self._solve(task_text, known, low)
        if used is not None:
            action["evidence"] = " ".join(s for s in (F.quote(k, known) for k in used) if s)
        return _dump(action)

    def _checker(self, task_text, visible, known, low, messages):
        action, _ = self._solve(task_text, known, low)
        return _dump(action)

    def _worker(self, task_text, visible, known, low, messages):
        if P.LINE_RX.search(task_text):
            kb = P.KB(known)
            try:
                used = P.solve_lines(task_text, kb)
            except P.Missing as miss:
                if not low:
                    return _dump(P.next_action(miss.key, known))
                kb = P.KB(known, lenient=True)
                used = P.solve_lines(task_text, kb)
        else:
            action, used = self._solve(task_text, known, low)
            if used is None:
                return _dump(action)
        return _dump({"report": " ".join(s for s in (F.quote(k, known) for k in used) if s)})

    # --- roles without a tool loop ----------------------------------------------------
    def _planner(self, task_text, visible, known, low, messages):
        q = P.parse_question(task_text)
        first = "Find the list of companies the question is about in its sector directory or city register."
        if q and P.TEMPLATE[q[0]][1] == "depth":
            first = "Follow the chain of companies one hop at a time, starting from the named company."
        plan = (
            f"1. {first} 2. Read each document that holds a needed fact and quote the fact sentence. "
            "3. Compute the answer from the quoted facts only. 4. Reply with the answer and the evidence."
        )
        return _dump({"plan": plan})

    def _lead(self, task_text, visible, known, low, messages, max_output=512):
        q = P.parse_question(task_text)
        if q is None:
            return _dump({"answer": "unknown"})
        kind, params = q
        if "Worker reports:" in visible:
            return _dump({"answer": P.solve(kind, params, P.KB(known, lenient=True))})
        if kind not in P.WORKER_LINES:  # a chain cannot be split, so one worker follows it
            return _dump({"plan": [P.question(kind, **params)]})
        key = ("sector_members", params["S"]) if "S" in params else ("city_members", params["C"])
        if key not in known:
            if low:
                return _dump({"answer": "unknown"})
            return _dump(P.next_action(key, known))
        members = list(known[key])
        k = min(5, max(3, math.ceil(len(members) / 3)))
        plan = []
        for i in range(k):
            group = members[i::k]
            lines = [line.format(x=x) for x in group for line in P.WORKER_LINES[kind]]
            docs = F.quote(key, {**known, key: tuple(group)}).split(": ", 1)[1]
            plan.append(
                "Find these facts and quote each fact sentence exactly as written:\n"
                + "\n".join(f"- {line}" for line in lines)
                + f"\nDocument ids: {docs}"
            )
        text = _dump({"plan": plan})
        if count_tokens(text) > max_output:  # too long for one reply: drop the document hints
            text = _dump({"plan": [p.split("\nDocument ids:")[0] for p in plan]})
        return text


class ReplayMiss(RuntimeError):
    pass


class ChatModel:
    """An OpenAI-compatible chat model with a cache keyed by the hash of each request.

    mode "record" sends cache misses to the provider and stores the answer.
    mode "replay" never touches the network and fails on a miss.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        cache_dir: Path,
        mode: str = "replay",
        key_env: str = "GROQ_API_KEY",
        timeout: float = 60.0,
        max_retries: int = 5,
    ):
        local = base_url.startswith(("http://127.0.0.1", "http://localhost"))
        if not (base_url.startswith("https://") or local):
            raise ValueError("base_url must be https, or http on localhost for tests")
        self.name, self.base_url, self.mode = model, base_url.rstrip("/"), mode
        self.cache_dir, self.key_env, self.timeout, self.max_retries = (
            Path(cache_dir),
            key_env,
            timeout,
            max_retries,
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def request(self, messages, max_output) -> dict:
        return {"model": self.name, "messages": messages, "max_tokens": max_output, "temperature": 0}

    def complete(self, messages: list[dict], max_output: int) -> tuple[str, dict]:
        req = self.request(messages, max_output)
        body = json.dumps(req, sort_keys=True, ensure_ascii=False).encode()
        path = self.cache_dir / f"{hashlib.sha256(body).hexdigest()}.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
        elif self.mode != "record":
            raise ReplayMiss(f"no recording for request {path.name}")
        else:
            raw = self._send(body)
            if not raw.get("choices"):
                raise RuntimeError("provider answered with no choices, so nothing was cached")
            tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(raw, sort_keys=True, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        text = raw["choices"][0]["message"].get("content") or ""
        usage = raw.get("usage") or {}
        return text, {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "provider_usage": True,
        }

    def _send(self, body: bytes) -> dict:
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        wait = 2.0
        for attempt in range(self.max_retries):
            url = f"{self.base_url}/chat/completions"  # scheme checked in __init__
            req = urllib.request.Request(url, data=body, headers=headers)  # noqa: S310
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 (fixed https base url)
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.max_retries - 1:
                    time.sleep(wait)
                    wait *= 2
                    continue
                raise
        raise RuntimeError("unreachable")
