from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import ChunkSettings


HEADING_RE = re.compile(r'(?m)^#{1,6}\s+.+$')


@dataclass(frozen=True)
class ChunkSlice:
  text: str
  char_start: int
  char_end: int


def estimate_tokens(text: str) -> int:
  # Fast deterministic heuristic suitable for chunk sizing.
  return max(1, len(text) // 4)


def split_markdown_blocks(markdown: str) -> list[tuple[int, int]]:
  if not markdown.strip():
    return []

  matches = list(HEADING_RE.finditer(markdown))
  if not matches:
    return [(0, len(markdown))]

  ranges: list[tuple[int, int]] = []
  for i, match in enumerate(matches):
    start = match.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
    ranges.append((start, end))
  return ranges


def _split_large_block(block_text: str, base_offset: int, max_chars: int) -> list[ChunkSlice]:
  paragraphs = re.split(r'\n\s*\n', block_text)
  pieces: list[ChunkSlice] = []

  cursor = 0
  buffer = ''
  buffer_start = 0

  for paragraph in paragraphs:
    para = paragraph.strip()
    if not para:
      cursor += len(paragraph) + 2
      continue

    candidate = f'{buffer}\n\n{para}'.strip() if buffer else para
    if len(candidate) > max_chars and buffer:
      end = buffer_start + len(buffer)
      pieces.append(ChunkSlice(text=buffer, char_start=base_offset + buffer_start, char_end=base_offset + end))
      buffer = para
      buffer_start = cursor
    elif len(candidate) > max_chars:
      pieces.append(ChunkSlice(text=para, char_start=base_offset + cursor, char_end=base_offset + cursor + len(para)))
      buffer = ''
      buffer_start = cursor + len(paragraph)
    else:
      buffer = candidate

    cursor += len(paragraph) + 2

  if buffer:
    end = buffer_start + len(buffer)
    pieces.append(ChunkSlice(text=buffer, char_start=base_offset + buffer_start, char_end=base_offset + end))

  return pieces


def chunk_markdown(markdown: str, settings: ChunkSettings) -> list[ChunkSlice]:
  if not markdown.strip():
    return []

  max_chars = settings.max_tokens * 4
  overlap_chars = settings.overlap_tokens * 4
  chunks: list[ChunkSlice] = []

  for start, end in split_markdown_blocks(markdown):
    block = markdown[start:end].strip()
    if not block:
      continue

    if len(block) <= max_chars:
      chunks.append(ChunkSlice(text=block, char_start=start, char_end=end))
      continue

    chunks.extend(_split_large_block(block, start, max_chars))

  if overlap_chars <= 0:
    return chunks

  overlapped: list[ChunkSlice] = []
  for i, chunk in enumerate(chunks):
    if i == 0:
      overlapped.append(chunk)
      continue
    prev_tail = chunks[i - 1].text[-overlap_chars:]
    merged_text = f'{prev_tail}\n\n{chunk.text}'.strip()
    overlapped.append(
      ChunkSlice(
        text=merged_text,
        char_start=max(0, chunk.char_start - overlap_chars),
        char_end=chunk.char_end,
      )
    )

  return overlapped
