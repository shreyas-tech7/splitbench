"""Write the 60 tasks from the answer key, and freeze them with the corpus.

20 breadth, 20 depth and 20 mixed tasks. Each type gives 7 or 6 tasks to the dev split
and the rest to the held-out split. Answers come from the structured facts, never from text.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from . import corpus
from . import facts as F
from . import procedures as P

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SEED = 7
DEV_PER_TYPE = {"breadth": 7, "depth": 7, "mixed": 6}


def _chain_ok(kb, kind, a):
    """Depth chains must visit distinct companies and exist in the key."""
    seen = [a]
    x = kb.f[("supplier", a)]
    seen.append(x)
    x = kb.f[("supplier", x)]
    seen.append(x)
    if kind == "city_sss":
        seen.append(kb.f[("supplier", x)])
    elif kind in ("rev_former_ss", "founded_chain5"):
        led = P.KB(kb.f, lenient=True).led_by(x)
        if led is None:
            return False
        seen.append(led)
        if kind == "founded_chain5":
            seen.append(kb.f[("supplier", led)])
    return len(set(seen)) == len(seen)


def _unique_best(kb, kind, p) -> bool:
    """Reject breadth and mixed tasks whose answer would tie."""
    f = kb.f
    if kind in ("top3_growth", "most_employees", "earliest_founded"):
        m = f[("sector_members", p["S"])]
        if kind == "top3_growth":
            vals = [f[("revenue", x, 2025)] / f[("revenue", x, 2024)] for x in m]
            return len(set(round(v, 9) for v in vals)) == len(vals)
        field = "employees" if kind == "most_employees" else "founded"
        vals = sorted((f[(field, x)] for x in m), reverse=kind == "most_employees")
        return vals[0] != vals[1]
    if kind == "top_supplier_rev":
        sups = {f[("supplier", x)] for x in f[("sector_members", p["S"])]}
        vals = sorted((f[("revenue", s, 2025)] for s in sups), reverse=True)
        return len(vals) < 2 or vals[0] != vals[1]
    return True


def candidates(kb: P.KB, rng: random.Random) -> dict[str, list]:
    f = kb.f
    out: dict[str, list] = {"breadth": [], "depth": [], "mixed": []}
    names = sorted(k[1] for k in f if k[0] == "sector")
    for s in F.SECTORS:
        for kind in ("top3_growth", "most_employees", "count_growth", "earliest_founded"):
            if _unique_best(kb, kind, {"S": s}):
                out["breadth"].append((kind, {"S": s}))
        for c in F.CITIES:
            members = f[("sector_members", s)]
            hits = sum(f[("city", f[("supplier", x)])] == c for x in members)
            if 2 <= hits <= len(members) - 2:
                out["mixed"].append(("supcity_total", {"S": s, "C": c}))
        if _unique_best(kb, "top_supplier_rev", {"S": s}):
            out["mixed"].append(("top_supplier_rev", {"S": s}))
        for y in (1990, 2000, 2010):
            members = f[("sector_members", s)]
            n = sum(f[("founded", f[("supplier", x)])] < y for x in members)
            if 2 <= n <= len(members) - 2:
                out["mixed"].append(("count_sup_founded", {"S": s, "Y": str(y)}))
    for c in F.CITIES:
        out["breadth"].append(("city_total", {"C": c}))
    for kind in ("ceo_ss", "city_sss", "rev_former_ss", "founded_chain5"):
        for a in names:
            if _chain_ok(kb, kind, a):
                out["depth"].append((kind, {"A": a}))
    for v in out.values():
        rng.shuffle(v)
    return out


def _pick(pool: list, n: int) -> list:
    """Take n tasks, cycling through the kinds so each kind is used."""
    by_kind: dict[str, list] = {}
    for kind, p in pool:
        by_kind.setdefault(kind, []).append((kind, p))
    picked, kinds = [], sorted(by_kind)
    while len(picked) < n:
        for k in kinds:
            if by_kind[k] and len(picked) < n:
                picked.append(by_kind[k].pop(0))
    return picked


def build(seed: int = SEED):
    docs, comps = corpus.generate(seed)
    kb = P.KB(corpus.key_facts(comps))
    rng = random.Random(seed + 1)
    pools = candidates(kb, rng)
    tasks = []
    for ttype in ("breadth", "depth", "mixed"):
        chosen = _pick(pools[ttype], 20)
        rng.shuffle(chosen)
        for i, (kind, p) in enumerate(chosen):
            k = P.KB(kb.f)
            answer = P.solve(kind, p, k)
            tasks.append(
                {
                    "id": f"T{len(tasks) + 1:02d}",
                    "type": ttype,
                    "kind": kind,
                    "params": p,
                    "question": P.question(kind, **p),
                    "answer": answer,
                    "answer_kind": P.TEMPLATE[kind][3],
                    "evidence": [list(key) for key in k.used],
                    "split": "dev" if i < DEV_PER_TYPE[ttype] else "heldout",
                }
            )
    return docs, tasks


def evidence_keys(task) -> list:
    return [tuple(e) for e in task["evidence"]]


def write(seed: int = SEED, out: Path = DATA) -> str:
    docs, tasks = build(seed)
    out.mkdir(parents=True, exist_ok=True)
    corpus_text = "".join(json.dumps(d, sort_keys=True) + "\n" for d in corpus.as_rows(docs))
    tasks_text = json.dumps(tasks, indent=1, sort_keys=True) + "\n"
    (out / "corpus.jsonl").write_text(corpus_text, encoding="utf-8")
    (out / "tasks.json").write_text(tasks_text, encoding="utf-8")
    digest = frozen_digest(corpus_text, tasks_text)
    (out / "FROZEN.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def frozen_digest(corpus_text: str, tasks_text: str) -> str:
    return hashlib.sha256((corpus_text + tasks_text).encode()).hexdigest()


def load(data: Path = DATA):
    docs = [corpus.Doc(**json.loads(line)) for line in (data / "corpus.jsonl").read_text().splitlines()]
    tasks = json.loads((data / "tasks.json").read_text())
    return docs, tasks
