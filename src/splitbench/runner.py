"""Run the study: every architecture on every task of a split, at each budget level.

Runs are appended to a JSONL file as they finish, so a stopped study resumes where it
stopped. Transcripts hold every prompt: each agent's system text and history, plus each
call's output and token counts.
"""

from __future__ import annotations

import gzip
import json
import platform
import time
from pathlib import Path

from . import agents, metrics
from . import tasks as T
from .budget import Budget
from .tools import Corpus

RESULTS = T.ROOT / "results"
# Chosen on the 20 dev tasks before any held-out run. See DECISIONS.md.
BUDGETS = {"tight": (10_000, 20), "loose": (45_000, 40)}
ARCH_ORDER = ["single", "orchestrator", "pipeline", "scratchpad"]


def transcript(run) -> dict:
    """Each agent's system text, history and result, plus every event in order.

    A prompt is the system text, a prefix of the history and the budget line, so this
    holds every prompt without storing each one again."""
    ags = [
        {
            "id": a.id,
            "role": a.role,
            "system": a.system,
            "history": a.history,
            "scratchpad": a.scratchpad,
            "result": a.result,
            "stopped": a.stopped,
        }
        for a in run.all_agents
    ]
    keep = (
        "seq",
        "agent",
        "event",
        "output",
        "input_tokens",
        "output_tokens",
        "grant",
        "action",
        "state",
        "reason",
    )
    return {"agents": ags, "events": [{k: e[k] for k in keep if k in e} for e in run.log.events]}


def run_one(task, arch, model, corpus, level, parallel="lockstep"):
    max_tokens, max_calls = BUDGETS[level]
    budget = Budget(max_tokens, max_calls)
    run = agents.ARCHS[arch](task, model, corpus, budget, parallel=parallel)
    ok = metrics.correct(run.answer, task)
    hand = metrics.handoff(run, task)
    model_calls = sum(1 for e in run.log.events if e["event"] == "model")
    rec = {
        "task": task["id"],
        "type": task["type"],
        "kind": task["kind"],
        "split": task["split"],
        "arch": arch,
        "level": level,
        "model": model.name,
        "answer": run.answer,
        "correct": ok,
        "tokens": budget.used_tokens,
        "tool_calls": budget.tool_calls,
        "model_calls": model_calls,
        "critical_calls": run.critical_calls,
        "stopped": run.stopped,
        "hit_cap": any(e["event"] == "stop" for e in run.log.events),
        "repeats": metrics.repeats(run),
        "handoff": hand,
        "mast": metrics.mast_tag(run, task, ok, hand),
        "seconds": round(run.seconds, 3),
    }
    assert budget.used_tokens <= max_tokens and budget.tool_calls <= max_calls
    return rec, transcript(run)


def safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-." else "_" for ch in name)


def runs_path(model_name: str, split: str, out: Path = RESULTS) -> Path:
    return out / f"runs-{safe(model_name)}-{split}.jsonl"


def load_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def study(
    model,
    split: str = "heldout",
    levels=("tight", "loose"),
    archs=ARCH_ORDER,
    parallel="lockstep",
    out: Path = RESULTS,
    limit: int | None = None,
    log=print,
) -> Path:
    docs, tasks = T.load()
    corpus = Corpus(docs)
    chosen = [t for t in tasks if split == "all" or t["split"] == split][:limit]
    out.mkdir(parents=True, exist_ok=True)
    path = runs_path(model.name, split, out)
    done = {(r["task"], r["arch"], r["level"]) for r in load_runs(path)}
    tpath = out / "transcripts" / f"{safe(model.name)}-{split}.jsonl"
    tpath.parent.mkdir(parents=True, exist_ok=True)
    n_new = 0
    with path.open("a", encoding="utf-8") as f, tpath.open("a", encoding="utf-8") as tf:
        for level in levels:
            for t in chosen:
                for arch in archs:
                    if (t["id"], arch, level) in done:
                        continue
                    rec, tr = run_one(t, arch, model, corpus, level, parallel)
                    f.write(json.dumps(rec, sort_keys=True) + "\n")
                    f.flush()
                    tf.write(
                        json.dumps({"task": t["id"], "arch": arch, "level": level, **tr}, sort_keys=True)
                        + "\n"
                    )
                    n_new += 1
    log(
        f"{n_new} new runs, {len(done)} resumed, file {path.relative_to(T.ROOT) if path.is_relative_to(T.ROOT) else path}"
    )
    return path


def finish_transcripts(model_name: str, split: str, out: Path = RESULTS) -> Path | None:
    """Gzip the transcript file with a fixed timestamp, so the same runs give the same bytes."""
    src = out / "transcripts" / f"{safe(model_name)}-{split}.jsonl"
    if not src.exists():
        return None
    dst = src.with_suffix(".jsonl.gz")
    rows = sorted(src.read_text(encoding="utf-8").splitlines())
    with open(dst, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as g:
        g.write(("\n".join(rows) + "\n").encode())
    src.unlink()
    return dst


def meta() -> dict:
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {"date": time.strftime("%Y-%m-%d"), "cpu": cpu, "python": platform.python_version()}
