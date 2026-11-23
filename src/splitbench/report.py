"""Turn result files into the summary, the report and the generated blocks of the README.

Nobody types a number into the README. Each block sits between
`<!-- splitbench:NAME -->` and `<!-- /splitbench:NAME -->` and this module rewrites it.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from . import corpus, metrics, runner
from . import tasks as T

ROOT = T.ROOT
ARCHS = runner.ARCH_ORDER
TYPES = ["breadth", "depth", "mixed"]
LABEL = {
    "single": "Single agent",
    "orchestrator": "Orchestrator and workers",
    "pipeline": "Pipeline",
    "scratchpad": "Single agent with scratchpad",
}
BLOCK = re.compile(r"(<!-- splitbench:(\w+) -->\n)(.*?)(<!-- /splitbench:\2 -->)", re.S)


def one(x: float, sign: bool = False) -> str:
    """One decimal, halves rounded up, so 9.45 and 9.575 round the same way."""
    d = Decimal(repr(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{d:+}" if sign else f"{d}"


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def summarize(runs: list[dict], meta: dict) -> dict:
    out = {"meta": meta, "levels": {}}
    for level in runner.BUDGETS:
        rs = [r for r in runs if r["level"] == level]
        if not rs:
            continue
        by = {a: sorted((r for r in rs if r["arch"] == a), key=lambda r: r["task"]) for a in ARCHS}
        lv = {
            "budget": {"tokens": runner.BUDGETS[level][0], "tool_calls": runner.BUDGETS[level][1]},
            "archs": {},
            "paired": {},
        }
        for a, xs in by.items():
            if not xs:
                continue
            k, n = sum(r["correct"] for r in xs), len(xs)
            toks = [r["tokens"] for r in xs]
            loss = [r["handoff"]["loss"] for r in xs if r["handoff"] and r["handoff"]["found"]]
            dropped = [r["handoff"]["dropped"] for r in xs if r["handoff"] and r["handoff"]["found"]]
            lv["archs"][a] = {
                "n": n,
                "success": k / n,
                "success_ci": metrics.wilson(k, n),
                "by_type": {
                    t: {
                        "k": sum(r["correct"] for r in xs if r["type"] == t),
                        "n": sum(1 for r in xs if r["type"] == t),
                        "tokens": _mean([r["tokens"] for r in xs if r["type"] == t]),
                    }
                    for t in TYPES
                },
                "tokens": sum(toks) / n,
                "tokens_ci": metrics.bootstrap_mean(toks),
                "tool_calls": sum(r["tool_calls"] for r in xs) / n,
                "critical_calls": sum(r["critical_calls"] for r in xs) / n,
                "hit_cap": sum(r["hit_cap"] for r in xs),
                "handoff_loss": sum(loss) / len(loss) if loss else None,
                "handoff_dropped": sum(dropped) / len(dropped) if dropped else None,
                "handoff_runs": len(loss),
                "mast": dict(sorted(Counter(r["mast"] for r in xs if r["mast"]).items())),
            }
        base = {r["task"]: r for r in by["single"]}
        for a in ARCHS[1:]:
            pairs = [(r, base[r["task"]]) for r in by[a] if r["task"] in base]
            if not pairs:
                continue
            ds = [int(r["correct"]) - int(b["correct"]) for r, b in pairs]
            dt = [r["tokens"] - b["tokens"] for r, b in pairs]
            lv["paired"][a] = {
                "n": len(pairs),
                "success_diff": sum(ds) / len(ds),
                "success_diff_ci": metrics.bootstrap_mean(ds, seed=1),
                "token_diff": sum(dt) / len(dt),
                "token_diff_ci": metrics.bootstrap_mean(dt, seed=2),
            }
        out["levels"][level] = lv
    return out


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def guide(summary: dict) -> list[str]:
    """Which design to pick for each task shape at each budget.

    Most tasks solved wins. A tie goes to the design that used fewer tokens on that
    task shape. The single agent is the default, so a team design is named only when
    it beats the single agent on success, or ties it and costs fewer tokens."""
    lines = []
    for level, lv in summary["levels"].items():
        for t in TYPES:
            rows = []
            for a, s in lv["archs"].items():
                bt = s["by_type"][t]
                rows.append((bt["k"] / bt["n"] if bt["n"] else 0, -bt["tokens"], a))
            single = next((r for r in rows if r[2] == "single"), None)
            if single is None:
                continue
            best = max(rows)
            head = f"- **{t.capitalize()} tasks, {level} budget:** "
            if best[2] == "single":
                lines.append(
                    head + f"single agent ({pct(single[0])} solved). No team design solved more "
                    "or matched it for fewer tokens."
                )
            elif best[0] > single[0]:
                lines.append(
                    head + f"{LABEL[best[2]].lower()} ({pct(best[0])} solved, against "
                    f"{pct(single[0])} for the single agent)."
                )
            else:
                saved = round(best[1] - single[1])
                lines.append(
                    head + f"{LABEL[best[2]].lower()}. It solved the same share as the single agent "
                    f"({pct(best[0])}) with {saved:,} fewer tokens per task."
                )
    return lines


# --- Markdown blocks ------------------------------------------------------------------
def _ci(lo, hi, f=pct):
    return f"{f(lo)} to {f(hi)}"


def results_table(summary: dict) -> str:
    out = []
    for level, lv in summary["levels"].items():
        b = lv["budget"]
        out.append(
            f"**{level.capitalize()} budget:** {b['tokens']:,} tokens and {b['tool_calls']} tool calls per task, "
            "shared by every agent in the run.\n"
        )
        out.append(
            "| Architecture | Solved (95% CI) | Breadth | Depth | Mixed | Tokens per task (95% CI) | "
            "Tool calls | Calls on the critical path | Handoff loss |"
        )
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for a, s in lv["archs"].items():
            bt = s["by_type"]
            loss = "n/a" if s["handoff_loss"] is None else pct(s["handoff_loss"])
            out.append(
                f"| {LABEL[a]} | {pct(s['success'])} ({_ci(*s['success_ci'])}) | "
                + " | ".join(f"{bt[t]['k']}/{bt[t]['n']}" for t in TYPES)
                + f" | {s['tokens']:,.0f} ({_ci(*s['tokens_ci'], f=lambda x: f'{x:,.0f}')}) | {one(s['tool_calls'])} | "
                f"{one(s['critical_calls'])} | {loss} |"
            )
        out.append("")
    return "\n".join(out)


def paired_table(summary: dict) -> str:
    out = [
        "| Budget | Compared with the single agent | Tasks | Change in solved share (95% CI) | "
        "Change in tokens per task (95% CI) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for level, lv in summary["levels"].items():
        for a, p in lv["paired"].items():
            lo, hi = p["success_diff_ci"]
            tlo, thi = p["token_diff_ci"]
            out.append(
                f"| {level} | {LABEL[a]} | {p['n']} | {one(p['success_diff'] * 100, True)} points "
                f"({one(lo * 100, True)} to {one(hi * 100, True)}) | {p['token_diff']:+,.0f} ({tlo:+,.0f} to {thi:+,.0f}) |"
            )
    return "\n".join(out) + "\n"


def mast_table(summary: dict) -> str:
    out = [
        "| Budget | Architecture | Failed runs | FC1 specification | FC2 inter-agent | FC3 verification |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for level, lv in summary["levels"].items():
        for a, s in lv["archs"].items():
            m = s["mast"]
            out.append(
                f"| {level} | {LABEL[a]} | {s['n'] - round(s['success'] * s['n'])} | {m.get('FC1', 0)} | "
                f"{m.get('FC2', 0)} | {m.get('FC3', 0)} |"
            )
    return "\n".join(out) + "\n"


def cost_table(summary: dict) -> str:
    out = [
        "| Budget | Architecture | Tokens per task | Tokens per solved task | Runs that hit a cap |",
        "| --- | --- | --- | --- | --- |",
    ]
    for level, lv in summary["levels"].items():
        for a, s in lv["archs"].items():
            solved = round(s["success"] * s["n"])
            per = f"{s['tokens'] * s['n'] / solved:,.0f}" if solved else "no task solved"
            out.append(f"| {level} | {LABEL[a]} | {s['tokens']:,.0f} | {per} | {s['hit_cap']} of {s['n']} |")
    return "\n".join(out) + "\n"


def status_line(summary: dict, oracle: dict) -> str:
    m = summary["meta"]
    tail = f" The oracle solves {oracle['correct']} of {oracle['n']} tasks.\n"
    if m["model"].startswith("scripted"):
        return (
            f"**Status:** v0.1.0-rc1. All numbers below come from the scripted model `{m['model']}`, not from "
            f"an LLM, run on {m['date']} with corpus seed {m['seed']} on the {m['n_tasks']} held-out tasks. "
            "No free-model run happened yet, because the build machine had no provider key and its network "
            "proxy refused the free providers." + tail
        )
    return (
        f"**Status:** v0.1.0-rc1. All numbers below come from `{m['model']}`, recorded on {m['date']} with "
        f"corpus seed {m['seed']} on {m['n_tasks']} held-out tasks, and replayed from the cache." + tail
    )


def setup_block() -> str:
    """Corpus, task and budget sizes, read from the frozen files and the runner."""
    docs, tasks = T.load()
    count = Counter(t["type"] for t in tasks)
    split = Counter(t["split"] for t in tasks)
    lines = [
        f"- **Corpus:** {len(docs)} invented documents about {corpus.N_COMPANIES} invented companies, "
        f"from seed {T.SEED}.",
        f"- **Tasks:** {len(tasks)} with exact answers: {count['breadth']} breadth, {count['depth']} depth "
        f"and {count['mixed']} mixed. {split['dev']} are for development and {split['heldout']} are held out.",
    ]
    for level, (tok, calls) in runner.BUDGETS.items():
        lines.append(
            f"- **{level.capitalize()} budget:** {tok:,} tokens and {calls} tool calls per task, "
            "shared by every agent in the run."
        )
    return "\n".join(lines) + "\n"


def blocks(summary: dict, oracle: dict) -> dict[str, str]:
    return {
        "setup": setup_block(),
        "status": status_line(summary, oracle),
        "results": results_table(summary),
        "paired": paired_table(summary),
        "mast": mast_table(summary),
        "cost": cost_table(summary),
        "guide": "\n".join(guide(summary)) + "\n",
        "seeds": seeds_table(summary),
    }


def fill(text: str, values: dict[str, str]) -> str:
    def sub(m):
        name = m.group(2)
        return m.group(1) + values[name] + m.group(4) if name in values else m.group(0)

    return BLOCK.sub(sub, text)


def html_page(summary: dict, oracle: dict) -> str:
    rows = []
    for level, lv in summary["levels"].items():
        for a, s in lv["archs"].items():
            loss = "n/a" if s["handoff_loss"] is None else pct(s["handoff_loss"])
            rows.append(
                f"<tr><td>{level}</td><td>{html.escape(LABEL[a])}</td><td>{pct(s['success'])}</td>"
                f"<td>{_ci(*s['success_ci'])}</td><td>{s['tokens']:,.0f}</td><td>{one(s['critical_calls'])}</td>"
                f"<td>{loss}</td></tr>"
            )
    guide_html = "".join(f"<li>{html.escape(g[2:]).replace('**', '')}</li>" for g in guide(summary))
    m = summary["meta"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>splitbench results</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1b1f24; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #d0d7de; padding: 6px 8px; text-align: left; }}
th {{ background: #f6f8fa; }}
.note {{ color: #57606a; }}
</style>
</head>
<body>
<h1 id="splitbench">splitbench results</h1>
<p class="note">Scripted model {html.escape(m["model"])}, {m["date"]}, corpus seed {m["seed"]}, {m["n_tasks"]} held-out
tasks. These numbers measure the protocols, not any LLM. The oracle solves {oracle["correct"]} of {oracle["n"]} tasks.</p>
<table>
<tr><th>Budget</th><th>Architecture</th><th>Solved</th><th>95% CI</th><th>Tokens per task</th>
<th>Critical-path calls</th><th>Handoff loss</th></tr>
{"".join(rows)}
</table>
<h2 id="guide">Decision guide</h2>
<ul>{guide_html}</ul>
<p class="note">Generated by <code>splitbench report</code> from results/summary-{html.escape(runner.safe(m["model"]))}-heldout.json.
See <a href="REPORT.md">the full report</a>.</p>
</body>
</html>
"""


REPORT_TEMPLATE = """# splitbench report

This file is generated by `splitbench report`. Do not edit it by hand.

<!-- splitbench:status -->
<!-- /splitbench:status -->

## Results on the held-out tasks

<!-- splitbench:results -->
<!-- /splitbench:results -->

## Paired differences

Each architecture runs the same tasks as the single agent, so each task gives one paired difference.

<!-- splitbench:paired -->
<!-- /splitbench:paired -->

## Cost

<!-- splitbench:cost -->
<!-- /splitbench:cost -->

## Failure tags (MAST groups)

<!-- splitbench:mast -->
<!-- /splitbench:mast -->

## Decision guide

<!-- splitbench:guide -->
<!-- /splitbench:guide -->

## Second corpus seed

The same study on a corpus and task set built from another seed, in memory. The frozen files stay as they are. Each cell counts solved held-out tasks.

<!-- splitbench:seeds -->
<!-- /splitbench:seeds -->
"""

TARGETS = ["README.md", "docs/REPORT.md", "docs/INTERVIEW_QA.md"]


def summary_path(model_name: str) -> Path:
    return ROOT / "results" / f"summary-{runner.safe(model_name)}-heldout.json"


def load_summary(model_name: str) -> tuple[dict, dict]:
    summary = json.loads(summary_path(model_name).read_text())
    oracle = json.loads((ROOT / "results" / "oracle.json").read_text())
    return summary, oracle


def render(model_name: str = "scripted-v1") -> dict[Path, str]:
    """The text every generated file should hold now."""
    summary, oracle = load_summary(model_name)
    values = blocks(summary, oracle)
    out = {}
    for rel in TARGETS:
        p = ROOT / rel
        base = (
            p.read_text(encoding="utf-8")
            if p.exists()
            else (REPORT_TEMPLATE if rel == "docs/REPORT.md" else "")
        )
        if base:
            out[p] = fill(base, values)
    out[ROOT / "docs" / "index.html"] = html_page(summary, oracle)
    return out


def other_seeds(model_name: str) -> list[dict]:
    """Solved counts from held-out runs on corpora built from other seeds."""
    out = []
    for path in sorted((ROOT / "results").glob(f"runs-{runner.safe(model_name)}-heldout-seed*.jsonl")):
        runs = runner.load_runs(path)
        seed = int(path.stem.rsplit("seed", 1)[1])
        levels = {}
        for level in runner.BUDGETS:
            levels[level] = {
                a: {
                    "k": sum(r["correct"] for r in runs if r["level"] == level and r["arch"] == a),
                    "n": sum(1 for r in runs if r["level"] == level and r["arch"] == a),
                }
                for a in ARCHS
            }
        out.append({"seed": seed, "levels": levels})
    return out


def seeds_table(summary: dict) -> str:
    seeds = summary.get("other_seeds") or []
    if not seeds:
        return "No run on another corpus seed yet.\n"
    head = f"| Budget | Architecture | Seed {summary['meta']['seed']} |" + "".join(
        f" Seed {x['seed']} |" for x in seeds
    )
    lines = [head, "| --- | --- | --- |" + " --- |" * len(seeds)]
    for level, lv in summary["levels"].items():
        for a, st in lv["archs"].items():
            k = sum(b["k"] for b in st["by_type"].values())
            row = f"| {level} | {LABEL[a]} | {k} of {st['n']} |"
            for x in seeds:
                c = x["levels"][level][a]
                row += f" {c['k']} of {c['n']} |"
            lines.append(row)
    return "\n".join(lines) + "\n"


def write_summary(model_name: str = "scripted-v1") -> Path:
    runs = runner.load_runs(runner.runs_path(model_name, "heldout"))
    meta_path = ROOT / "results" / f"meta-{runner.safe(model_name)}-heldout.json"
    meta = json.loads(meta_path.read_text())
    s = summarize(runs, meta)
    s["other_seeds"] = other_seeds(model_name)
    path = summary_path(model_name)
    path.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path
