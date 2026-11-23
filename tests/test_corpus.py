from splitbench import corpus, facts


def test_counts_and_determinism():
    docs, comps = corpus.generate(7)
    assert len(docs) == 301 and len(comps) == 58
    again, _ = corpus.generate(7)
    assert [d.text for d in docs] == [d.text for d in again]
    other, _ = corpus.generate(8)
    assert [d.text for d in docs] != [d.text for d in other]


def test_every_key_fact_parses_back_from_the_text():
    """Broken case: a generator sentence the parser cannot read, so a fact exists only in the key."""
    docs, comps = corpus.generate(7)
    kb = {}
    for d in docs:
        kb.update(facts.parse(f"Document {d.id} | {d.title}\n{d.text}"))
    key = corpus.key_facts(comps)
    assert {k: kb.get(k) for k in key} == key


def test_former_companies_are_unique():
    _, comps = corpus.generate(7)
    formers = [c.former for c in comps.values() if c.former]
    assert len(formers) == len(set(formers)) and len(formers) >= 30


def test_quote_round_trips():
    kb = {
        ("revenue", "Varn Labs", 2025): 412,
        ("supplier", "Varn Labs"): "Kest Group",
        ("city", "Kest Group"): "Maraview",
    }
    text = " ".join(facts.quote(k, kb) for k in kb)
    assert {k: facts.parse(text)[k] for k in kb} == kb
