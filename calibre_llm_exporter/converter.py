from __future__ import annotations

import json
import posixpath
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from .chunking import chunk_markdown, estimate_tokens
from .schemas import BookMeta, ChunkRecord, ChunkSettings, SourceRef


class SimpleMarkdownParser(HTMLParser):
  def __init__(self):
    super().__init__(convert_charrefs=True)
    self.parts: list[str] = []
    self._link_stack: list[str] = []
    self._list_depth = 0
    self._ordered_list_stack: list[int] = []
    self._skip_depth = 0

  def handle_starttag(self, tag: str, attrs):
    if tag in {'script', 'style', 'head'}:
      self._skip_depth += 1
      return
    if self._skip_depth > 0:
      return

    attrs_map = {k: v for k, v in attrs}
    if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
      level = int(tag[1])
      self.parts.append('\n' + ('#' * level) + ' ')
    elif tag in {'p', 'div', 'section', 'article'}:
      self.parts.append('\n\n')
    elif tag == 'br':
      self.parts.append('  \n')
    elif tag in {'strong', 'b'}:
      self.parts.append('**')
    elif tag in {'em', 'i'}:
      self.parts.append('*')
    elif tag == 'code':
      self.parts.append('`')
    elif tag == 'pre':
      self.parts.append('\n```\n')
    elif tag == 'li':
      prefix = '  ' * max(0, self._list_depth - 1)
      if self._ordered_list_stack:
        index = self._ordered_list_stack[-1]
        self.parts.append(f'\n{prefix}{index}. ')
        self._ordered_list_stack[-1] = index + 1
      else:
        self.parts.append(f'\n{prefix}- ')
    elif tag in {'ul', 'ol'}:
      self._list_depth += 1
      if tag == 'ol':
        self._ordered_list_stack.append(1)
    elif tag == 'a':
      self._link_stack.append(attrs_map.get('href', '').strip())
      self.parts.append('[')
    elif tag == 'img':
      alt = attrs_map.get('alt', '').strip() or 'image'
      src = attrs_map.get('src', '').strip()
      self.parts.append(f'![{alt}]({src})')
    elif tag == 'table':
      self.parts.append('\n\n')
    elif tag == 'tr':
      self.parts.append('\n| ')
    elif tag in {'th', 'td'}:
      pass

  def handle_endtag(self, tag: str):
    if tag in {'script', 'style', 'head'}:
      self._skip_depth = max(0, self._skip_depth - 1)
      return
    if self._skip_depth > 0:
      return

    if tag in {'strong', 'b'}:
      self.parts.append('**')
    elif tag in {'em', 'i'}:
      self.parts.append('*')
    elif tag == 'code':
      self.parts.append('`')
    elif tag == 'pre':
      self.parts.append('\n```\n')
    elif tag in {'ul', 'ol'}:
      self._list_depth = max(0, self._list_depth - 1)
      if tag == 'ol' and self._ordered_list_stack:
        self._ordered_list_stack.pop()
    elif tag in {'th', 'td'}:
      self.parts.append(' | ')
    elif tag == 'a':
      href = self._link_stack.pop() if self._link_stack else ''
      self.parts.append(f']({href})' if href else ']')

  def handle_data(self, data: str):
    if self._skip_depth > 0:
      return
    cleaned = unescape(data)
    if cleaned.strip():
      self.parts.append(cleaned)

  def markdown(self) -> str:
    text = ''.join(self.parts)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    return text.strip() + '\n'


@dataclass(frozen=True)
class SpineItem:
  href: str
  title: str
  markdown: str


def html_to_markdown(html: str) -> str:
  parser = SimpleMarkdownParser()
  parser.feed(html)
  return parser.markdown()


def normalize_markdown(md: str) -> str:
  md = re.sub(r'\u00a0', ' ', md)
  md = re.sub(r'\n{3,}', '\n\n', md)
  md = re.sub(r'[ \t]+\n', '\n', md)
  return md.strip() + '\n'


def _ns(tag: str) -> str:
  return '{urn:oasis:names:tc:opendocument:xmlns:container}' + tag


def _read_container_rootfile(zf: zipfile.ZipFile) -> str:
  container_xml = zf.read('META-INF/container.xml')
  root = ET.fromstring(container_xml)
  rootfile = root.find(f'.//{_ns("rootfile")}')
  if rootfile is None:
    raise ValueError('Invalid EPUB: missing rootfile in container.xml')
  full_path = rootfile.attrib.get('full-path')
  if not full_path:
    raise ValueError('Invalid EPUB: rootfile has no full-path')
  return full_path


def _read_opf_spine(zf: zipfile.ZipFile, opf_path: str) -> tuple[dict[str, tuple[str, str]], list[str], str, str, list[str]]:
  opf_xml = zf.read(opf_path)
  root = ET.fromstring(opf_xml)
  ns = {
    'opf': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/',
  }

  manifest: dict[str, tuple[str, str]] = {}
  for item in root.findall('.//opf:manifest/opf:item', ns):
    manifest[item.attrib['id']] = (item.attrib.get('href', ''), item.attrib.get('media-type', ''))

  spine_ids = [item.attrib['idref'] for item in root.findall('.//opf:spine/opf:itemref', ns) if 'idref' in item.attrib]

  title = (root.findtext('.//dc:title', default='', namespaces=ns) or '').strip() or 'Untitled'
  language = (root.findtext('.//dc:language', default='unknown', namespaces=ns) or '').strip() or 'unknown'
  authors = [el.text.strip() for el in root.findall('.//dc:creator', ns) if el.text and el.text.strip()]
  return manifest, spine_ids, title, language, authors


def extract_spine_markdown(epub_path: Path) -> tuple[list[SpineItem], str, str, list[str]]:
  with zipfile.ZipFile(epub_path, 'r') as zf:
    opf_path = _read_container_rootfile(zf)
    opf_dir = posixpath.dirname(opf_path)
    manifest, spine_ids, title, language, authors = _read_opf_spine(zf, opf_path)

    items: list[SpineItem] = []
    for idref in spine_ids:
      href, media_type = manifest.get(idref, ('', ''))
      if not href or not media_type.startswith('application/xhtml+xml'):
        continue

      normalized_href = posixpath.normpath(posixpath.join(opf_dir, href))
      raw_html = zf.read(normalized_href).decode('utf-8', errors='replace')
      markdown = normalize_markdown(html_to_markdown(raw_html))

      chapter_title = _first_heading(markdown) or f'Chapter {len(items) + 1}'
      items.append(SpineItem(href=normalized_href, title=chapter_title, markdown=markdown))

  if not items:
    raise ValueError('No XHTML chapters found in EPUB spine')

  return items, title, language, authors


def _first_heading(markdown: str) -> str:
  for line in markdown.splitlines():
    if line.startswith('#'):
      return line.lstrip('#').strip()
  return ''


def _slug(value: str) -> str:
  slug = re.sub(r'[^a-zA-Z0-9]+', '-', value).strip('-').lower()
  return slug or 'book'


def build_records(
  *,
  book_id: str,
  title: str,
  authors: list[str],
  spine_items: Iterable[SpineItem],
  settings: ChunkSettings,
) -> list[ChunkRecord]:
  records: list[ChunkRecord] = []
  base_slug = _slug(f'{book_id}-{title}')

  for chapter_idx, item in enumerate(spine_items, start=1):
    chunks = chunk_markdown(item.markdown, settings)
    for chunk_idx, chunk in enumerate(chunks, start=1):
      chunk_id = f'{base_slug}/ch-{chapter_idx:03d}/ck-{chunk_idx:03d}'
      has_table = '|' in chunk.text and '\n| ' in chunk.text
      has_footnotes = bool(re.search(r'\[\^\d+\]|footnote', chunk.text, flags=re.IGNORECASE))
      anchors = re.findall(r'(?m)^#{1,6}\s+(.+)$', chunk.text)
      normalized_anchors = [_slug(anchor) for anchor in anchors if anchor.strip()]

      record = ChunkRecord(
        id=chunk_id,
        book_id=book_id,
        title=title,
        authors=authors,
        chapter_idx=chapter_idx,
        chapter_title=item.title,
        section_path=[item.title],
        chunk_idx=chunk_idx,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        token_estimate=estimate_tokens(chunk.text),
        text=chunk.text,
        text_plain=re.sub(r'[#*_`\[\]()!>-]', '', chunk.text),
        has_table=has_table,
        has_footnotes=has_footnotes,
        source=SourceRef(epub_href=item.href, anchors=normalized_anchors),
      )
      records.append(record)

  return records


def export_epub_for_llm(
  epub_path: str,
  output_dir: str,
  *,
  book_id: str,
  settings: ChunkSettings | None = None,
) -> dict[str, str]:
  settings = settings or ChunkSettings()
  epub = Path(epub_path)
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)

  spine_items, title, language, authors = extract_spine_markdown(epub)
  merged_markdown = '\n\n---\n\n'.join(item.markdown for item in spine_items).strip() + '\n'

  safe_name = _slug(title)
  md_path = out / f'{safe_name}.md'
  jsonl_path = out / f'{safe_name}.chunks.jsonl'
  meta_path = out / f'{safe_name}.meta.json'

  records = build_records(
    book_id=book_id,
    title=title,
    authors=authors,
    spine_items=spine_items,
    settings=settings,
  )

  md_path.write_text(merged_markdown, encoding='utf-8')
  with jsonl_path.open('w', encoding='utf-8') as f:
    for record in records:
      f.write(json.dumps(record.to_json_dict(), ensure_ascii=False) + '\n')

  meta = BookMeta(
    book_id=book_id,
    title=title,
    authors=authors,
    language=language,
    source_epub_path=str(epub),
  )
  meta_path.write_text(json.dumps(meta.to_json_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

  return {
    'markdown': str(md_path),
    'jsonl': str(jsonl_path),
    'meta': str(meta_path),
  }
