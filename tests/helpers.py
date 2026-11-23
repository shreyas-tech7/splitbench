"""Shared test helpers."""

from splitbench import tasks as T
from splitbench.tools import Corpus

DOCS, TASKS = T.load()
CORPUS = Corpus(DOCS)
BY_ID = {t["id"]: t for t in TASKS}


def first(kind=None, ttype=None, split=None):
    return next(
        t
        for t in TASKS
        if (kind is None or t["kind"] == kind)
        and (ttype is None or t["type"] == ttype)
        and (split is None or t["split"] == split)
    )
