"""Task templates, and the procedures that answer them from a set of known facts.

A procedure reads facts through `KB.get`. When a fact is not known yet, `get` raises
`Missing`, and `next_action` says which tool call would find it. The oracle solver,
the scripted model and the answer key all use these same procedures.
"""

from __future__ import annotations

import re

from . import facts as F


class Missing(Exception):
    def __init__(self, key):
        super().__init__(key)
        self.key = key


class KB:
    def __init__(self, facts: dict, lenient: bool = False):
        self.f = facts
        self.lenient = lenient
        self.used: list = []

    def get(self, key):
        if key in self.f:
            if key not in self.used:
                self.used.append(key)
            return self.f[key]
        if self.lenient:
            return None
        raise Missing(key)

    def members(self, key) -> tuple:
        return self.get(key) or ()

    def led_by(self, company):
        """The company whose chief executive previously led `company`."""
        for key, val in list(self.f.items()):
            if key[0] == "former" and val == company:
                person = key[1]
                for k2, v2 in list(self.f.items()):
                    if k2[0] == "ceo" and v2 == person:
                        self.get(key)
                        self.get(k2)
                        return k2[1]
        if self.lenient:
            return None
        raise Missing(("led_by", company))


S = rf"(?P<S>{F.SECTOR})"
C = rf"(?P<C>{F.CITY})"
A = rf"(?P<A>{F.COMPANY})"
Y = r"(?P<Y>\d{4})"

# kind, task type, question format, answer kind
TEMPLATES = [
    (
        "top3_growth",
        "breadth",
        "Which three {S} companies grew revenue the most from fiscal 2024 to fiscal 2025, by percentage? "
        "Answer with the three company names, highest growth first, separated by commas.",
        "list3",
    ),
    (
        "city_total",
        "breadth",
        "What was the total fiscal 2025 revenue, in millions of dollars, of the companies headquartered in {C}? "
        "Answer with a whole number.",
        "number",
    ),
    (
        "most_employees",
        "breadth",
        "Which {S} company has the most employees? Answer with the company name.",
        "name",
    ),
    (
        "count_growth",
        "breadth",
        "How many {S} companies reported higher revenue in fiscal 2025 than in fiscal 2024? "
        "Answer with a whole number.",
        "number",
    ),
    (
        "earliest_founded",
        "breadth",
        "Which {S} company was founded earliest? Answer with the company name.",
        "name",
    ),
    (
        "ceo_ss",
        "depth",
        "Who is the chief executive of the key supplier of the key supplier of {A}? "
        "Answer with the person's name.",
        "name",
    ),
    (
        "city_sss",
        "depth",
        "In which city is the key supplier of the key supplier of the key supplier of {A} headquartered? "
        "Answer with the city name.",
        "name",
    ),
    (
        "rev_former_ss",
        "depth",
        "What was the fiscal 2025 revenue, in millions of dollars, of the company whose chief executive "
        "previously led the key supplier of the key supplier of {A}? Answer with a whole number.",
        "number",
    ),
    (
        "founded_chain5",
        "depth",
        "In which year was the key supplier of the company whose chief executive previously led the key "
        "supplier of the key supplier of {A} founded? Answer with the year.",
        "number",
    ),
    (
        "supcity_total",
        "mixed",
        "What is the total fiscal 2025 revenue, in millions of dollars, of the {S} companies whose key "
        "supplier is headquartered in {C}? Answer with a whole number.",
        "number",
    ),
    (
        "top_supplier_rev",
        "mixed",
        "Among the key suppliers of the {S} companies, which one reported the highest fiscal 2025 revenue? "
        "Answer with the company name.",
        "name",
    ),
    (
        "count_sup_founded",
        "mixed",
        "How many {S} companies have a key supplier that was founded before {Y}? Answer with a whole number.",
        "number",
    ),
]
TEMPLATE = {t[0]: t for t in TEMPLATES}


def _rx(fmt: str) -> re.Pattern:
    body = re.escape(fmt.split("?")[0] + "?")
    for name, grp in (("S", S), ("C", C), ("A", A), ("Y", Y)):
        body = body.replace(re.escape("{" + name + "}"), grp)
    return re.compile(body)


QUESTION_RX = [(t[0], _rx(t[2])) for t in TEMPLATES]


def question(kind: str, **params) -> str:
    return TEMPLATE[kind][2].format(**params)


def parse_question(text: str):
    """Find the first task question in `text`. Returns (kind, params) or None."""
    best = None
    for kind, rx in QUESTION_RX:
        m = rx.search(text)
        if m and (best is None or m.start() < best[2]):
            best = (kind, {k: v for k, v in m.groupdict().items() if v}, m.start())
    return None if best is None else (best[0], best[1])


def _growth(kb, n):
    a, b = kb.get(("revenue", n, 2024)), kb.get(("revenue", n, 2025))
    if a is None or b is None:
        return None
    return b / a - 1


def _sup(kb, n):
    return kb.get(("supplier", n))


def solve(kind: str, p: dict, kb: KB) -> str:
    if kind == "top3_growth":
        g = [(x, _growth(kb, x)) for x in kb.members(("sector_members", p["S"]))]
        g = sorted([t for t in g if t[1] is not None], key=lambda t: -t[1])
        return ", ".join(x for x, _ in g[:3]) or "unknown"
    if kind == "city_total":
        vals = [kb.get(("revenue", x, 2025)) for x in kb.members(("city_members", p["C"]))]
        return str(sum(v for v in vals if v is not None))
    if kind == "most_employees":
        e = [(x, kb.get(("employees", x))) for x in kb.members(("sector_members", p["S"]))]
        e = [t for t in e if t[1] is not None]
        return max(e, key=lambda t: t[1])[0] if e else "unknown"
    if kind == "count_growth":
        g = [_growth(kb, x) for x in kb.members(("sector_members", p["S"]))]
        return str(sum(1 for v in g if v is not None and v > 0))
    if kind == "earliest_founded":
        e = [(x, kb.get(("founded", x))) for x in kb.members(("sector_members", p["S"]))]
        e = [t for t in e if t[1] is not None]
        return min(e, key=lambda t: t[1])[0] if e else "unknown"
    if kind in ("ceo_ss", "city_sss", "rev_former_ss", "founded_chain5"):
        x = _sup(kb, p["A"])
        x = x and _sup(kb, x)
        if kind == "ceo_ss":
            return (x and kb.get(("ceo", x))) or "unknown"
        if kind == "city_sss":
            x = x and _sup(kb, x)
            return (x and kb.get(("city", x))) or "unknown"
        x = x and kb.led_by(x)
        if kind == "rev_former_ss":
            v = x and kb.get(("revenue", x, 2025))
            return str(v) if v else "unknown"
        x = x and _sup(kb, x)
        v = x and kb.get(("founded", x))
        return str(v) if v else "unknown"
    if kind == "supcity_total":
        total = 0
        for x in kb.members(("sector_members", p["S"])):
            s = _sup(kb, x)
            if s and kb.get(("city", s)) == p["C"]:
                total += kb.get(("revenue", x, 2025)) or 0
        return str(total)
    if kind == "top_supplier_rev":
        best = None
        for x in kb.members(("sector_members", p["S"])):
            s = _sup(kb, x)
            v = s and kb.get(("revenue", s, 2025))
            if v and (best is None or v > best[1]):
                best = (s, v)
        return best[0] if best else "unknown"
    if kind == "count_sup_founded":
        n = 0
        for x in kb.members(("sector_members", p["S"])):
            s = _sup(kb, x)
            v = s and kb.get(("founded", s))
            n += bool(v and v < int(p["Y"]))
        return str(n)
    raise ValueError(kind)


DOC_FOR = {
    "sector": "profile",
    "city": "profile",
    "founded": "profile",
    "ceo": "profile",
    "employees": "profile",
    "supplier": "f2025",
}
SEARCH_WORDS = {
    "profile": "company profile",
    "f2024": "annual filing fiscal 2024",
    "f2025": "annual filing fiscal 2025",
}


def next_action(key, facts: dict) -> dict | None:
    """The tool call that would reveal `key`, given the facts already visible."""
    if key[0] in ("sector_members", "city_members"):
        did = facts.get(("dirdoc", key[1]))
        if did:
            return {"tool": "read_doc", "doc_id": did}
        word = "Sector directory" if key[0] == "sector_members" else "City register"
        return {"tool": "search", "query": f"{word} {key[1]}"}
    if key[0] == "led_by":
        for k, did in facts.items():
            if k[0] == "doc" and k[2] == "lnews" and k[1] != key[1] and ("read", did) not in facts:
                return {"tool": "read_doc", "doc_id": did}
        return {"tool": "search", "query": f"leadership news previously led {key[1]}"}
    kind = f"f{key[2]}" if key[0] == "revenue" else DOC_FOR[key[0]]
    did = facts.get(("doc", key[1], kind))
    if did:
        return {"tool": "read_doc", "doc_id": did}
    return {"tool": "search", "query": f"{key[1]} {SEARCH_WORDS[kind]}"}


# What a worker must find for each member company, by task kind (used by the orchestrator's plan).
WORKER_LINES = {
    "top3_growth": ["fiscal 2024 revenue of {x}", "fiscal 2025 revenue of {x}"],
    "count_growth": ["fiscal 2024 revenue of {x}", "fiscal 2025 revenue of {x}"],
    "city_total": ["fiscal 2025 revenue of {x}"],
    "most_employees": ["employee count of {x}"],
    "earliest_founded": ["founding year of {x}"],
    "supcity_total": ["fiscal 2025 revenue of {x}", "headquarters city of the key supplier of {x}"],
    "top_supplier_rev": ["fiscal 2025 revenue of the key supplier of {x}"],
    "count_sup_founded": ["founding year of the key supplier of {x}"],
}
LINE_RX = re.compile(
    rf"- (fiscal (2024|2025) revenue|employee count|founding year|headquarters city|chief executive|key supplier)"
    rf" of (the key supplier of )?({F.COMPANY})"
)
FIELD = {
    "employee count": "employees",
    "founding year": "founded",
    "headquarters city": "city",
    "chief executive": "ceo",
    "key supplier": "supplier",
}


def solve_lines(text: str, kb: KB) -> list:
    """Resolve every worker line in `text`. Returns the fact keys used. Raises Missing."""
    for m in LINE_RX.finditer(text):
        field, year, via, company = m.groups()
        target = kb.get(("supplier", company)) if via else company
        if target is None:
            continue
        if year:
            kb.get(("revenue", target, int(year)))
        else:
            kb.get((FIELD[field], target))
    return kb.used
