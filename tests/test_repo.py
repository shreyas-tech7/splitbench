"""Checks on the README and docs: section order, generated blocks, writing rules."""

import json
import re
import struct

from splitbench import report
from splitbench import tasks as T

ROOT = T.ROOT
README = (ROOT / "README.md").read_text(encoding="utf-8")
DOCS = [
    ROOT / "README.md",
    *sorted((ROOT / "docs").glob("*.md")),
    ROOT / "DECISIONS.md",
    ROOT / "CONTRIBUTING.md",
]

SECTIONS = [
    "<!-- splitbench:status -->",
    "## The problem",
    "```mermaid",
    "## Results",
    "## Cost per task",
    "## Run it in ten minutes",
    "## Limits",
    "## Glossary",
    "## Related work",
    "## How this was built",
]


def prose(text: str) -> str:
    """Text with generated blocks, code, links and markup removed."""
    text = report.BLOCK.sub("", text)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return text


def test_readme_sections_in_order():
    pos = [README.index(s) for s in SECTIONS]
    assert pos == sorted(pos)


def test_readme_links_the_build_prompt_and_lists_open_human_checks():
    assert "docs/build/BUILD_PROMPT.md" in README
    assert "not done yet" in README


def test_generated_blocks_match_the_result_files():
    for path, text in report.render().items():
        assert path.read_text(encoding="utf-8") == text, f"run splitbench report: {path.name}"


def test_readme_numbers_come_from_the_summary():
    summary = json.loads((ROOT / "results" / "summary-scripted-v1-heldout.json").read_text())
    single = summary["levels"]["loose"]["archs"]["single"]
    assert report.pct(single["success"]) in README
    assert f"{single['tokens']:,.0f}" in README


def test_no_typed_numbers_in_readme_prose():
    body = re.sub(r"FC\d", "", prose(README))  # MAST group labels are names, not numbers
    assert not re.findall(r"\d", body), re.findall(r".{20}\d.{20}", body)


def test_no_dash_punctuation_or_semicolons_in_docs():
    for path in DOCS:
        if not path.exists():
            continue
        text = prose(path.read_text(encoding="utf-8"))
        text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("|"))
        assert "—" not in text and "–" not in text, path.name
        assert not re.search(r"\s-\s", text.replace("\n- ", "\n")), path.name
        assert ";" not in text, path.name


def test_social_preview_size():
    data = (ROOT / "docs" / "social-preview.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (1280, 640)
