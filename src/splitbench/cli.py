"""Command line: splitbench <command>."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from . import models, oracle, report, runner
from . import tasks as T
from .tools import Corpus

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.1-8b-instant"),
    "openrouter": (
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        "meta-llama/llama-3.3-70b-instruct:free",
    ),
}


def cmd_generate(a):
    print("frozen digest", T.write(a.seed))


def cmd_check_frozen(a):
    docs, tasks = T.build(T.SEED)
    from . import corpus

    corpus_text = "".join(json.dumps(d, sort_keys=True) + "\n" for d in corpus.as_rows(docs))
    tasks_text = json.dumps(tasks, indent=1, sort_keys=True) + "\n"
    want = (T.DATA / "FROZEN.sha256").read_text().strip()
    got = T.frozen_digest(corpus_text, tasks_text)
    disk = T.frozen_digest((T.DATA / "corpus.jsonl").read_text(), (T.DATA / "tasks.json").read_text())
    print("frozen", want, "\nregenerated", got, "\non disk", disk)
    return 0 if want == got == disk else 1


def cmd_oracle(a):
    docs, tasks = T.load()
    c = Corpus(docs)
    rows = []
    for t in tasks:
        ans, calls = oracle.solve(t, c)
        rows.append({"task": t["id"], "answer": ans, "correct": ans == t["answer"], "tool_calls": calls})
    res = {"n": len(rows), "correct": sum(r["correct"] for r in rows), "runs": rows}
    (runner.RESULTS / "oracle.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(f"oracle: {res['correct']} of {res['n']} right")
    return 0 if res["correct"] == res["n"] else 1


def _model(a):
    if a.provider == "scripted":
        return models.ScriptedModel()
    base, key_env, default = PROVIDERS[a.provider]
    return models.ChatModel(
        a.model or default, base, runner.RESULTS / "cache" / a.provider, mode=a.mode, key_env=key_env
    )


def cmd_run(a):
    model = _model(a)
    split = a.split
    path = runner.study(
        model,
        split=split,
        levels=a.levels,
        archs=a.archs,
        limit=a.limit,
        parallel="lockstep" if a.provider == "scripted" else a.parallel,
    )
    meta = {
        **runner.meta(),
        "model": model.name,
        "seed": T.SEED,
        "n_tasks": len({r["task"] for r in runner.load_runs(path)}),
        "bootstrap_seed": 0,
    }
    (runner.RESULTS / f"meta-{model.name}-{split}.json").write_text(
        json.dumps(meta, indent=1, sort_keys=True) + "\n"
    )
    runner.finish_transcripts(model.name, split)


def cmd_report(a):
    report.write_summary(a.model_name)
    for path, text in report.render(a.model_name).items():
        path.write_text(text, encoding="utf-8")
        print("wrote", path.relative_to(T.ROOT))


def cmd_readme(a):
    if not a.check:
        return cmd_report(a)
    stale = [
        p
        for p, text in report.render(a.model_name).items()
        if not p.exists() or p.read_text(encoding="utf-8") != text
    ]
    for p in stale:
        print("out of date:", p.relative_to(T.ROOT))
    print("generated files are up to date" if not stale else "run: splitbench report")
    return 1 if stale else 0


def cmd_probe(a):
    rows = []
    for name, (base, key_env, _) in PROVIDERS.items():
        url = f"{base}/models"
        try:
            out = subprocess.run(
                ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-m", "10", url],
                capture_output=True,
                text=True,
                timeout=20,
            )
            code = out.stdout.strip() or out.stderr.strip()[-80:]
        except (OSError, subprocess.TimeoutExpired) as e:
            code = str(e)
        rows.append(
            {"provider": name, "url": url, "result": code, "key_set": key_env in __import__("os").environ}
        )
        print(name, url, code, "key set" if rows[-1]["key_set"] else "no key")
    (runner.RESULTS / "probe.json").write_text(json.dumps({**runner.meta(), "probes": rows}, indent=1) + "\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="splitbench", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write the corpus, tasks and frozen digest")
    g.add_argument("--seed", type=int, default=T.SEED)
    g.set_defaults(fn=cmd_generate)
    sub.add_parser("check-frozen", help="regenerate and compare with the frozen files").set_defaults(
        fn=cmd_check_frozen
    )
    sub.add_parser("oracle", help="solve every task with the tools and no model").set_defaults(fn=cmd_oracle)
    r = sub.add_parser("run", help="run the study")
    r.add_argument("--provider", default="scripted", choices=["scripted", *PROVIDERS])
    r.add_argument("--model", default=None)
    r.add_argument("--mode", default="replay", choices=["record", "replay"])
    r.add_argument("--split", default="heldout", choices=["dev", "heldout", "all"])
    r.add_argument("--levels", nargs="+", default=list(runner.BUDGETS))
    r.add_argument("--archs", nargs="+", default=runner.ARCH_ORDER)
    r.add_argument("--limit", type=int, default=None, help="only the first N tasks of the split")
    r.add_argument("--parallel", default="threads", choices=["threads", "lockstep"])
    r.set_defaults(fn=cmd_run)
    for name in ("report", "readme"):
        x = sub.add_parser(name, help="write the summary, report and README blocks")
        x.add_argument("--model-name", default="scripted-v1")
        x.add_argument("--check", action="store_true", help="fail if a generated file is out of date")
        x.set_defaults(fn=cmd_report if name == "report" else cmd_readme)
    sub.add_parser("probe", help="check whether the record-mode hosts answer").set_defaults(fn=cmd_probe)
    a = p.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
