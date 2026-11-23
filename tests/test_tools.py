from helpers import CORPUS

from splitbench import facts


def test_search_finds_a_title_first():
    out = CORPUS.search("Sector directory Biotech")
    first = out.splitlines()[1]
    assert "Sector directory: Biotech" in first


def test_search_returns_at_most_five_ids_and_titles():
    lines = CORPUS.search("annual filing fiscal 2025").splitlines()[1:]
    assert 1 <= len(lines) <= 5 and all(" | " in x for x in lines)


def test_read_doc_and_bad_ids():
    text = CORPUS.read_doc("D001")
    assert text.startswith("Document D001 |") and facts.parse(text)
    assert "No document" in CORPUS.read_doc("D999")
    assert "Unknown tool" in CORPUS.call({"tool": "delete"})
