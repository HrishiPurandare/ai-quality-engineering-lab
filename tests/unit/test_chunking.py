from pathlib import Path

import pytest

from app.chunking import chunk_directory, chunk_document, split_sections, window
from app.config import settings

DOC = """# Title

Intro text that is not in any section.

## First

Alpha paragraph.

## Second

Beta paragraph one.

Beta paragraph two.
"""


def test_split_sections_returns_heading_and_body_pairs():
    assert split_sections(DOC) == [
        ("First", "Alpha paragraph."),
        ("Second", "Beta paragraph one.\n\nBeta paragraph two."),
    ]


def test_split_sections_drops_text_before_first_section():
    assert all("Intro" not in body for _, body in split_sections(DOC))


def test_window_keeps_short_text_in_one_piece():
    assert window("one\n\ntwo", size=100, overlap=10) == ["one\n\ntwo"]


def test_window_splits_long_text_and_repeats_overlap():
    text = "\n\n".join(["a" * 50, "b" * 50, "c" * 50])
    pieces = window(text, size=60, overlap=10)
    assert len(pieces) == 3
    assert pieces[1].startswith("a" * 10)  # tail of the previous piece carried over
    assert all(len(p) <= 60 + 10 + 2 for p in pieces)


def test_window_never_drops_an_oversized_paragraph():
    assert window("x" * 500, size=100, overlap=10) == ["x" * 500]


def test_window_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        window("text", size=10, overlap=10)


def test_chunk_document_prefixes_title_and_section(tmp_path: Path):
    doc = tmp_path / "policy.md"
    doc.write_text(DOC)
    chunks = chunk_document(doc, size=800, overlap=100)
    assert [c.section for c in chunks] == ["First", "Second"]
    assert chunks[0].text.startswith("Title - First")
    assert chunks[0].source == "policy.md"
    assert chunks[0].id == "policy::0"


def test_real_policy_corpus_chunks_are_unique_and_non_empty():
    chunks = chunk_directory(settings.policies_dir, 800, 120)
    assert len(chunks) >= 20
    assert len({c.id for c in chunks}) == len(chunks)
    assert {c.source for c in chunks} == {p.name for p in settings.policies_dir.glob("*.md")}
    assert all(c.text.strip() for c in chunks)
