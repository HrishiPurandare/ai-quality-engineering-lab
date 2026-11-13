"""Split policy documents into retrievable chunks.

Strategy: split each markdown file by `## ` section first (so a chunk never mixes
two topics), then cut long sections into overlapping windows on paragraph boundaries.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    section: str


def split_sections(markdown: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs for every `## ` section. Text before the first one is dropped."""
    parts = re.split(r"^## +(.+)$", markdown, flags=re.MULTILINE)
    # re.split with a capture group gives: [preamble, heading1, body1, heading2, body2, ...]
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def window(text: str, size: int, overlap: int) -> list[str]:
    """Pack paragraphs into windows of at most `size` chars, repeating ~`overlap` chars of context."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    windows: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) <= size or not current:
            current = candidate
            continue
        windows.append(current)
        tail = current[-overlap:] if overlap else ""
        current = f"{tail}\n\n{paragraph}".strip()
    if current:
        windows.append(current)
    return windows


def chunk_document(path: Path, size: int, overlap: int) -> list[Chunk]:
    markdown = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# +(.+)$", markdown, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem
    chunks: list[Chunk] = []
    for heading, body in split_sections(markdown):
        for piece in window(body, size, overlap):
            chunks.append(
                Chunk(
                    id=f"{path.stem}::{len(chunks)}",
                    # The heading is part of the embedded text: it carries a lot of the meaning.
                    text=f"{title} - {heading}\n\n{piece}",
                    source=path.name,
                    section=heading,
                )
            )
    return chunks


def chunk_directory(directory: Path, size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(chunk_document(path, size, overlap))
    return chunks
