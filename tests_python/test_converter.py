import json
from pathlib import Path

from calibre_llm_exporter.converter import export_epub_for_llm, extract_spine_markdown


FIXTURE = Path('test/fixtures/file-1.epub')


def test_extract_spine_markdown_has_chapters():
  items, title, language, authors = extract_spine_markdown(FIXTURE)
  assert len(items) > 0
  assert isinstance(title, str) and title
  assert isinstance(language, str) and language
  assert isinstance(authors, list)


def test_export_epub_for_llm_writes_expected_files(tmp_path: Path):
  out = export_epub_for_llm(str(FIXTURE), str(tmp_path), book_id='calibre:1')

  md_path = Path(out['markdown'])
  jsonl_path = Path(out['jsonl'])
  meta_path = Path(out['meta'])

  assert md_path.exists()
  assert jsonl_path.exists()
  assert meta_path.exists()

  lines = jsonl_path.read_text(encoding='utf-8').strip().splitlines()
  assert lines
  first = json.loads(lines[0])
  assert first['id'].startswith('calibre-1/')
  assert first['book_id'] == 'calibre:1'
  assert 'source' in first and 'epub_href' in first['source']
