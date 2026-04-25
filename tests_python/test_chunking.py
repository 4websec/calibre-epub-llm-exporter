from calibre_llm_exporter.chunking import chunk_markdown
from calibre_llm_exporter.schemas import ChunkSettings


def test_chunk_markdown_heading_split():
  text = '# A\n\n' + ('x' * 100) + '\n\n## B\n\n' + ('y' * 100)
  chunks = chunk_markdown(text, ChunkSettings(max_tokens=40, overlap_tokens=0))
  assert len(chunks) >= 2
  assert chunks[0].text.startswith('# A')


def test_chunk_markdown_overlap():
  text = '# A\n\n' + ('a ' * 500)
  chunks = chunk_markdown(text, ChunkSettings(max_tokens=50, overlap_tokens=10))
  assert len(chunks) > 1
  assert len(chunks[1].text) > len(chunks[0].text) / 2
