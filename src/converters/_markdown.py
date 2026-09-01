"""Shared Markdown preprocessing for document converters."""

from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_TOC_TITLES = {"目录", "table of contents", "toc"}


def strip_static_toc(markdown: str) -> str:
    """Remove authored TOC sections; native PDF/DOCX TOCs are generated later."""
    lines = markdown.splitlines(keepends=True)
    ranges: list[tuple[int, int]] = []
    fence: tuple[str, int] | None = None
    index = 0

    while index < len(lines):
        plain = lines[index].rstrip("\r\n")
        fence_match = _FENCE.match(plain)
        if fence_match:
            marker = fence_match.group(1)
            marker_kind = marker[0]
            if fence is None:
                fence = (marker_kind, len(marker))
            elif marker_kind == fence[0] and len(marker) >= fence[1]:
                fence = None
            index += 1
            continue

        heading = _HEADING.match(plain) if fence is None else None
        if (
            heading is None
            or len(heading.group(1)) == 1
            or heading.group(2).strip().casefold() not in _TOC_TITLES
        ):
            index += 1
            continue

        level = len(heading.group(1))
        end = index + 1
        nested_fence: tuple[str, int] | None = None
        while end < len(lines):
            candidate = lines[end].rstrip("\r\n")
            candidate_fence = _FENCE.match(candidate)
            if candidate_fence:
                marker = candidate_fence.group(1)
                marker_kind = marker[0]
                if nested_fence is None:
                    nested_fence = (marker_kind, len(marker))
                elif marker_kind == nested_fence[0] and len(marker) >= nested_fence[1]:
                    nested_fence = None
                end += 1
                continue
            next_heading = _HEADING.match(candidate) if nested_fence is None else None
            if next_heading is not None and len(next_heading.group(1)) <= level:
                break
            end += 1
        ranges.append((index, end))
        index = end

    if not ranges:
        return markdown

    kept: list[str] = []
    cursor = 0
    for start, end in ranges:
        kept.extend(lines[cursor:start])
        cursor = end
    kept.extend(lines[cursor:])

    return "".join(kept)


@contextmanager
def prepared_markdown_source(source: Path) -> Iterator[Path]:
    """Yield a temporary TOC-free source only when preprocessing is needed."""
    original = source.read_text(encoding="utf-8")
    prepared = strip_static_toc(original)
    if prepared == original:
        yield source
        return

    with tempfile.TemporaryDirectory(prefix="deepresearch-document-") as directory:
        temporary_source = Path(directory) / source.name
        temporary_source.write_text(prepared, encoding="utf-8")
        yield temporary_source
