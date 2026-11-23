"""The two tools every architecture gets: `search` (BM25 over the corpus) and `read_doc`."""

from __future__ import annotations

import math
import re
from collections import Counter

TOOL_TEXT = (
    "Tools:\n"
    '- search: {"tool": "search", "query": "<words>"} returns the ids and titles of the 5 best matching '
    "documents.\n"
    '- read_doc: {"tool": "read_doc", "doc_id": "D001"} returns the full text of one document.'
)
WORD = re.compile(r"[a-z0-9]+")
K = 5


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


class Corpus:
    def __init__(self, docs, k1: float = 1.5, b: float = 0.75):
        self.docs = {d.id: d for d in docs}
        self.k1, self.b = k1, b
        # Titles count twice, so a query that names a document's title finds it first.
        self.tf = {d.id: Counter(words(d.title) * 2 + words(d.text)) for d in docs}
        self.len = {i: sum(c.values()) for i, c in self.tf.items()}
        self.avg = sum(self.len.values()) / len(self.len)
        df = Counter(w for c in self.tf.values() for w in c)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def score(self, q: list[str], did: str) -> float:
        tf, dl, s = self.tf[did], self.len[did], 0.0
        for w in q:
            f = tf.get(w, 0)
            if f:
                s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
        return s

    def search(self, query: str, k: int = K) -> str:
        q = words(query)
        ranked = sorted(self.docs, key=lambda d: (-self.score(q, d), d))[:k]
        lines = [f"{d} | {self.docs[d].title}" for d in ranked if self.score(q, d) > 0]
        return "Search results:\n" + ("\n".join(lines) if lines else "no matches")

    def read_doc(self, doc_id: str) -> str:
        d = self.docs.get(str(doc_id).strip())
        if d is None:
            return f"No document with id {doc_id!r}."
        return f"Document {d.id} | {d.title}\n{d.text}"

    def call(self, action: dict) -> str:
        if action.get("tool") == "search":
            return self.search(str(action.get("query", "")))
        if action.get("tool") == "read_doc":
            return self.read_doc(action.get("doc_id", ""))
        return f"Unknown tool {action.get('tool')!r}. Use search or read_doc."
