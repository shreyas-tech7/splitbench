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
    if budget.used_tokens > max_tokens or budget.tool_calls > max_calls:
        raise RuntimeError(f"budget broken: {budget.used_tokens} tokens, {budget.tool_calls} tool calls")
    return rec, transcript(run)


def safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-." else "_" for ch in name)


def tag(split: str, seed: int | None = None) -> str:
    """File tag for a split. A corpus seed other than the frozen one adds a suffix."""
    return split if seed in (None, T.SEED) else f"{split}-seed{seed}"


def runs_path(model_name: str, split: str, out: Path = RESULTS, seed: int | None = None) -> Path:
    return out / f"runs-{safe(model_name)}-{tag(split, seed)}.jsonl"


def load_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a line cut by a hard stop; that run is simply run again
    return rows


def study(
    model,
    split: str = "heldout",
    levels=("tight", "loose"),
    archs=ARCH_ORDER,
    parallel="lockstep",
    out: Path = RESULTS,
    limit: int | None = None,
    log=print,
    seed: int | None = None,
) -> Path:
    """Run the study. `seed` rebuilds the corpus and tasks in memory from another seed,
    as a check that a result does not depend on one corpus. The frozen files stay as they are."""
    docs, tasks = T.load() if seed in (None, T.SEED) else T.build(seed)
    corpus = Corpus(docs)
    chosen = [t for t in tasks if split == "all" or t["split"] == split][:limit]
    out.mkdir(parents=True, exist_ok=True)
    path = runs_path(model.name, split, out, seed)
    done = {(r["task"], r["arch"], r["level"]) for r in load_runs(path)}
    tpath = out / "transcripts" / f"{safe(model.name)}-{tag(split, seed)}.jsonl"
    tpath.parent.mkdir(parents=True, exist_ok=True)
    n_new = 0
    with path.open("a", encoding="utf-8") as f, tpath.open("a", encoding="utf-8") as tf:
        for level in levels:
            for t in chosen:
                for arch in archs:
                    if (t["id"], arch, level) in done:
                        continue
                    rec, tr = run_one(t, arch, model, corpus, level, parallel)
                    # Transcript first, so a run never counts as done without its transcript.
                    tf.write(
                        json.dumps({"task": t["id"], "arch": arch, "level": level, **tr}, sort_keys=True)
                        + "\n"
                    )
                    tf.flush()
                    f.write(json.dumps(rec, sort_keys=True) + "\n")
                    f.flush()
                    n_new += 1
    log(
        f"{n_new} new runs, {len(done)} resumed, file {path.relative_to(T.ROOT) if path.is_relative_to(T.ROOT) else path}"
    )
    return path


def finish_transcripts(
    model_name: str, split: str, out: Path = RESULTS, seed: int | None = None
) -> Path | None:
    """Merge new transcript rows into the gzip archive, with a fixed timestamp.

    Rows already in the archive stay, so a resumed study keeps earlier transcripts.
    The same runs give the same bytes."""
    src = out / "transcripts" / f"{safe(model_name)}-{tag(split, seed)}.jsonl"
    dst = src.with_suffix(".jsonl.gz")
    rows = set()
    if dst.exists():
        rows.update(gzip.decompress(dst.read_bytes()).decode().splitlines())
    if src.exists():
        rows.update(src.read_text(encoding="utf-8").splitlines())
    rows.discard("")
    if not rows:
        return None
    with open(dst, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as g:
        g.write(("\n".join(sorted(rows)) + "\n").encode())
    if src.exists():
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
