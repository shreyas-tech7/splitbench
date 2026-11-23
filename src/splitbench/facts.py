"""Fact sentences: how facts are written in the corpus, and how text is parsed back into facts.

Every fact lives in one self-contained sentence. Agents quote these sentences in their
reports, so one parser reads documents, search results, notes and reports alike.
"""

from __future__ import annotations

import re

SECTORS = ["Biotech", "Fintech", "Logistics", "Energy", "Retail", "Robotics"]
CITIES = ["Port Ellery", "Maraview", "Lindhaven", "Corrow Bay", "Westmere"]
SUFFIXES = ["Labs", "Systems", "Group", "Works", "Holdings", "Dynamics", "Partners", "Industries"]

COMPANY = r"[A-Z][a-z]+ (?:" + "|".join(SUFFIXES) + ")"
PERSON = r"[A-Z][a-z]+ [A-Z][a-z]+"
SECTOR = "|".join(SECTORS)
CITY = "|".join(CITIES)


def s_profile(n, sector, city):
    return f"{n} is a {sector} company headquartered in {city}."


def s_founded(n, year):
    return f"{n} was founded in {year}."


def s_ceo(n, ceo):
    return f"The chief executive of {n} is {ceo}."


def s_employees(n, emp):
    return f"{n} employs {emp} people."


def s_revenue(n, year, rev):
    return f"In fiscal {year}, {n} reported revenue of ${rev} million."


def s_supplier(n, sup):
    return f"The key supplier of {n} is {sup}."


def s_former(ceo, n, former):
    return f"{ceo}, the chief executive of {n}, previously led {former}."


PATTERNS = [
    (re.compile(rf"({COMPANY}) is a ({SECTOR}) company headquartered in ({CITY})\."), "profile"),
    (re.compile(rf"({COMPANY}) was founded in (\d{{4}})\."), "founded"),
    (re.compile(rf"The chief executive of ({COMPANY}) is ({PERSON})\."), "ceo"),
    (re.compile(rf"({COMPANY}) employs (\d+) people\."), "employees"),
    (re.compile(rf"In fiscal (\d{{4}}), ({COMPANY}) reported revenue of \$(\d+) million\."), "revenue"),
    (re.compile(rf"The key supplier of ({COMPANY}) is ({COMPANY})\."), "supplier"),
    (re.compile(rf"({PERSON}), the chief executive of ({COMPANY}), previously led ({COMPANY})\."), "former"),
    (
        re.compile(
            rf"(D\d{{3}}) \| ({COMPANY}) (company profile|annual filing, fiscal 2024|annual filing, fiscal 2025|leadership news|product news)"
        ),
        "title",
    ),
    (re.compile(rf"(D\d{{3}}) \| (Sector directory|City register): ({SECTOR}|{CITY})"), "dirtitle"),
    (re.compile(rf"The ({SECTOR}) companies are: ([^.]*)\."), "sector_members"),
    (re.compile(rf"Companies headquartered in ({CITY}) are: ([^.]*)\."), "city_members"),
    (re.compile(r"Document (D\d{3}) \|"), "read"),
    # Short forms that agents write in reports.
    (re.compile(rf"({COMPANY}) is headquartered in ({CITY})\."), "city_short"),
    (re.compile(rf"({PERSON}) previously led ({COMPANY})\."), "former_short"),
]
DIR_ENTRY = re.compile(rf"({COMPANY}) \(profile (D\d{{3}}), filings (D\d{{3}}) and (D\d{{3}})\)")
KIND = {
    "company profile": "profile",
    "annual filing, fiscal 2024": "f2024",
    "annual filing, fiscal 2025": "f2025",
    "leadership news": "lnews",
    "product news": "pnews",
}


def parse(text: str) -> dict:
    """Return every fact found in `text` as {key: value}. Keys are tuples."""
    kb: dict = {}
    for rx, kind in PATTERNS:
        for m in rx.finditer(text):
            g = m.groups()
            if kind == "profile":
                kb[("sector", g[0])] = g[1]
                kb[("city", g[0])] = g[2]
            elif kind == "founded":
                kb[("founded", g[0])] = int(g[1])
            elif kind == "ceo":
                kb[("ceo", g[0])] = g[1]
            elif kind == "employees":
                kb[("employees", g[0])] = int(g[1])
            elif kind == "revenue":
                kb[("revenue", g[1], int(g[0]))] = int(g[2])
            elif kind == "supplier":
                kb[("supplier", g[0])] = g[1]
            elif kind == "former":
                kb[("ceo", g[1])] = g[0]
                kb[("former", g[0])] = g[2]
            elif kind == "read":
                kb[("read", g[0])] = True
            elif kind == "city_short":
                kb[("city", g[0])] = g[1]
            elif kind == "former_short":
                kb[("former", g[0])] = g[1]
            elif kind == "title":
                kb[("doc", g[1], KIND[g[2]])] = g[0]
            elif kind == "dirtitle":
                kb[("dirdoc", g[2])] = g[0]
            elif kind in ("sector_members", "city_members"):
                kb[(kind, g[0])] = tuple(e[0] for e in DIR_ENTRY.findall(g[1]))
    # Directory entries name each company's documents, wherever they are quoted.
    for name, prof, f24, f25 in DIR_ENTRY.findall(text):
        kb[("doc", name, "profile")] = prof
        kb[("doc", name, "f2024")] = f24
        kb[("doc", name, "f2025")] = f25
    return kb


def sentence(key, value) -> str | None:
    """Write one fact back as its canonical sentence (used when agents quote facts)."""
    k = key[0]
    if k == "revenue":
        return s_revenue(key[1], key[2], value)
    if k == "supplier":
        return s_supplier(key[1], value)
    if k == "founded":
        return s_founded(key[1], value)
    if k == "ceo":
        return s_ceo(key[1], value)
    if k == "employees":
        return s_employees(key[1], value)
    if k == "city":
        return f"{key[1]} is headquartered in {value}."
    if k == "former":
        return f"{key[1]} previously led {value}."
    return None


def quote(key, facts: dict) -> str | None:
    """Quote one known fact as its canonical sentence, including directory entries."""
    if key[0] in ("sector_members", "city_members"):
        entries = []
        for n in facts.get(key, ()):
            ids = [facts.get(("doc", n, k)) for k in ("profile", "f2024", "f2025")]
            entries.append(f"{n} (profile {ids[0]}, filings {ids[1]} and {ids[2]})" if all(ids) else n)
        lead = (
            f"The {key[1]} companies are"
            if key[0] == "sector_members"
            else (f"Companies headquartered in {key[1]} are")
        )
        return f"{lead}: {'; '.join(entries)}."
    if key not in facts:
        return None
    return sentence(key, facts[key])


def fact_lines(text: str) -> list[str]:
    """The lines and sentences of `text` that carry at least one fact."""
    out = []
    for line in text.splitlines():
        parts = [line] if "|" in line else re.split(r"(?<=\.) (?=[A-Z])", line)
        out.extend(p for p in parts if parse(p))
    return out
