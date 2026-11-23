"""Seeded generator for the invented-company corpus and its answer key.

58 companies, five documents each (profile, two annual filings, leadership news,
product news), plus six sector directories and five city registers: 301 documents.
The structured facts are the answer key. Every fact also appears in one sentence.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from . import facts as F

N_COMPANIES = 58
STEMS = (
    "Varn Orbin Kest Talo Brivo Quorr Lumen Zeph Marro Pell Sorin Vexa Halden Ivo Corra Nexo Tyrel Abri "
    "Mosk Fenn Ondra Rilo Siva Taron Uxel Wyra Yalo Zorin Calix Dorne Elvan Faro Gisel Hollo Jarvo Kiro "
    "Lorne Mira Nolan Opal Pryce Quinto Rhee Selka Tamsin Ulmo Verin Wexley Xandor Yorick Zellen Ashby "
    "Brenna Cato Delmar Esk Fable Grove Harlo Ister Jun Kael"
).split()
FIRST = "Ada Bram Cleo Dara Eli Fern Gus Hana Ivan Jo Kai Lena Milo Nora Omar Pia Quin Rosa Sami Tess".split()
LAST = "Quill Marsh Okafor Lind Arden Vos Kato Reyes Brandt Moss Ilves Nash Sato Fenwick Hale Oduya".split()
FILLER = [
    "The board met four times during the year.",
    "Management expects steady demand in its core markets.",
    "The company opened a new training center for staff.",
    "Auditors raised no material concerns.",
    "Freight costs stayed close to the prior year.",
    "The annual meeting will take place in the spring.",
    "Customer retention improved in the second half.",
    "The company paid no special dividend this year.",
]
PRODUCTS = [
    "a sensor kit",
    "a billing tool",
    "a cold-chain tracker",
    "a battery pack",
    "a store app",
    "a robot arm",
]


@dataclass
class Company:
    name: str
    sector: str
    city: str
    founded: int
    ceo: str
    employees: int
    rev2024: int
    rev2025: int
    supplier: str
    former: str | None  # the company the CEO previously led, if any
    partner: str


@dataclass
class Doc:
    id: str
    title: str
    text: str


def _companies(rng: random.Random) -> list[Company]:
    names, used = [], set()
    while len(names) < N_COMPANIES:
        n = f"{rng.choice(STEMS)} {rng.choice(F.SUFFIXES)}"
        stem = n.split()[0]
        if stem not in used:
            used.add(stem)
            names.append(n)
    ceos, seen = [], set()
    while len(ceos) < N_COMPANIES:
        c = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if c not in seen:
            seen.add(c)
            ceos.append(c)
    sectors = [F.SECTORS[i % len(F.SECTORS)] for i in range(N_COMPANIES)]
    cities = [F.CITIES[i % len(F.CITIES)] for i in range(N_COMPANIES)]
    rng.shuffle(sectors)
    rng.shuffle(cities)
    # Revenues and growth rates are drawn so that no two companies tie.
    revs24 = rng.sample(range(40, 2000), N_COMPANIES)
    growth = rng.sample(range(-300, 600), N_COMPANIES)  # tenths of a percent
    emps = rng.sample(range(80, 9000), N_COMPANIES)
    years = [rng.randrange(1975, 2020) for _ in range(N_COMPANIES)]
    out = []
    for i, n in enumerate(names):
        r24 = revs24[i]
        r25 = max(1, round(r24 * (1000 + growth[i]) / 1000))
        sup = rng.choice([m for m in names if m != n])
        partner = rng.choice([m for m in names if m != n])
        out.append(
            Company(n, sectors[i], cities[i], years[i], ceos[i], emps[i], r24, r25, sup, None, partner)
        )
    # About two thirds of the CEOs previously led another company. Each former company appears once.
    formers = rng.sample(names, 40)
    leaders = rng.sample(range(N_COMPANIES), 40)
    for li, fname in zip(leaders, formers, strict=True):
        if out[li].name != fname:
            out[li].former = fname
    return out


def generate(seed: int = 7) -> tuple[list[Doc], dict[str, Company]]:
    rng = random.Random(seed)
    comps = _companies(rng)
    docs: list[Doc] = []
    ids: dict[str, dict[str, str]] = {}

    def add(title, sentences):
        did = f"D{len(docs) + 1:03d}"
        docs.append(Doc(did, title, " ".join(sentences)))
        return did

    for c in comps:
        fill = rng.sample(FILLER, 6)
        ids[c.name] = {
            "profile": add(
                f"{c.name} company profile",
                [
                    F.s_profile(c.name, c.sector, c.city),
                    fill[0],
                    F.s_founded(c.name, c.founded),
                    F.s_ceo(c.name, c.ceo),
                    F.s_employees(c.name, c.employees),
                ],
            ),
            "f2024": add(
                f"{c.name} annual filing, fiscal 2024",
                [
                    f"This is the fiscal 2024 annual filing of {c.name}.",
                    fill[1],
                    fill[2],
                    F.s_revenue(c.name, 2024, c.rev2024),
                    fill[3],
                ],
            ),
            "f2025": add(
                f"{c.name} annual filing, fiscal 2025",
                [
                    f"This is the fiscal 2025 annual filing of {c.name}.",
                    fill[4],
                    F.s_revenue(c.name, 2025, c.rev2025),
                    fill[5],
                    F.s_supplier(c.name, c.supplier),
                ],
            ),
            "lnews": add(
                f"{c.name} leadership news",
                [
                    F.s_former(c.ceo, c.name, c.former)
                    if c.former
                    else F.s_ceo(c.name, c.ceo) + f" {c.ceo} has led {c.name} since joining it.",
                    "The leadership team will present at an industry forum next month.",
                ],
            ),
            "pnews": add(
                f"{c.name} product news",
                [
                    f"{c.name} launched {rng.choice(PRODUCTS)} built with its partner {c.partner}.",
                    "Early orders came from repeat customers.",
                ],
            ),
        }

    def entry(n):
        d = ids[n]
        return f"{n} (profile {d['profile']}, filings {d['f2024']} and {d['f2025']})"

    for s in F.SECTORS:
        members = sorted(c.name for c in comps if c.sector == s)
        add(f"Sector directory: {s}", [f"The {s} companies are: {'; '.join(entry(m) for m in members)}."])
    for city in F.CITIES:
        members = sorted(c.name for c in comps if c.city == city)
        add(
            f"City register: {city}",
            [f"Companies headquartered in {city} are: {'; '.join(entry(m) for m in members)}."],
        )
    return docs, {c.name: c for c in comps}


def key_facts(comps: dict[str, Company]) -> dict:
    """The answer key as fact tuples, in the same shape that `facts.parse` returns."""
    kb: dict = {}
    for c in comps.values():
        kb[("sector", c.name)] = c.sector
        kb[("city", c.name)] = c.city
        kb[("founded", c.name)] = c.founded
        kb[("ceo", c.name)] = c.ceo
        kb[("employees", c.name)] = c.employees
        kb[("revenue", c.name, 2024)] = c.rev2024
        kb[("revenue", c.name, 2025)] = c.rev2025
        kb[("supplier", c.name)] = c.supplier
        if c.former:
            kb[("former", c.ceo)] = c.former
    for s in F.SECTORS:
        kb[("sector_members", s)] = tuple(sorted(c.name for c in comps.values() if c.sector == s))
    for city in F.CITIES:
        kb[("city_members", city)] = tuple(sorted(c.name for c in comps.values() if c.city == city))
    return kb


def as_rows(docs: list[Doc]) -> list[dict]:
    return [asdict(d) for d in docs]
