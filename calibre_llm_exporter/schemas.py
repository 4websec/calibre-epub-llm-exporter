from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ChunkSettings:
  target_tokens: int = 800
  max_tokens: int = 1000
  overlap_tokens: int = 120


@dataclass(frozen=True)
class SourceRef:
  epub_href: str
  anchors: list[str]


@dataclass(frozen=True)
class ChunkRecord:
  id: str
  book_id: str
  title: str
  authors: list[str]
  chapter_idx: int
  chapter_title: str
  section_path: list[str]
  chunk_idx: int
  char_start: int
  char_end: int
  token_estimate: int
  text: str
  text_plain: str
  has_table: bool
  has_footnotes: bool
  source: SourceRef

  def to_json_dict(self) -> dict[str, Any]:
    data = asdict(self)
    return data


@dataclass(frozen=True)
class BookMeta:
  book_id: str
  title: str
  authors: list[str]
  language: str
  source_epub_path: str
  converter_version: str = 'epub-to-llm-exporter/0.1.0'

  def to_json_dict(self) -> dict[str, Any]:
    return {
      'book_id': self.book_id,
      'title': self.title,
      'authors': self.authors,
      'language': self.language,
      'source_epub_path': self.source_epub_path,
      'converter_version': self.converter_version,
      'created_at': datetime.now(timezone.utc).isoformat(),
    }
