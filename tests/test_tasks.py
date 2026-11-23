import subprocess
import sys
from collections import Counter

from helpers import TASKS

from splitbench import corpus
from splitbench import procedures as P
from splitbench import tasks as T


def test_frozen_files_match_the_generator():
    """Broken case: someone edits data/tasks.json or the generator after the freeze."""
    out = subprocess.run(
        [sys.executable, "-m", "splitbench.cli", "check-frozen"], capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stdout


def test_sixty_tasks_twenty_per_type_and_split():
    assert len(TASKS) == 60 and len({t["id"] for t in TASKS}) == 60
    assert Counter(t["type"] for t in TASKS) == {"breadth": 20, "depth": 20, "mixed": 20}
    assert Counter(t["split"] for t in TASKS) == {"dev": 20, "heldout": 40}
    assert set(t["kind"] for t in TASKS) == set(P.TEMPLATE)


def test_answers_come_from_the_key():
    _, comps = corpus.generate(T.SEED)
    key = corpus.key_facts(comps)
    for t in TASKS:
        assert P.solve(t["kind"], t["params"], P.KB(key)) == t["answer"]
        assert P.parse_question(t["question"]) == (t["kind"], t["params"])


def _docs(ev, key):
    """The documents a task's evidence lives in."""
    people = {k[1] for k in ev if k[0] == "former"}
    out = set()
    for k in ev:
        if k[0] == "supplier" or (k[0] == "revenue" and k[2] == 2025):
            out.add(("f2025", k[1]))
        elif k[0] == "revenue":
            out.add(("f2024", k[1]))
        elif k[0] == "ceo" and key[k] in people:
            out.add(("lnews", k[1]))
        elif k[0] in ("ceo", "city", "founded", "employees"):
            out.add(("profile", k[1]))
    return out


def test_breadth_tasks_cover_8_to_15_companies_and_depth_chains_3_to_5_documents():
    _, comps = corpus.generate(T.SEED)
    key = corpus.key_facts(comps)
    for t in TASKS:
        ev = T.evidence_keys(t)
        if t["type"] == "breadth":
            companies = {k[1] for k in ev if k[0] not in ("sector_members", "city_members")}
            assert 8 <= len(companies) <= 15, t["id"]
        if t["type"] == "depth":
            assert 3 <= len(_docs(ev, key)) <= 5, (t["id"], _docs(ev, key))
