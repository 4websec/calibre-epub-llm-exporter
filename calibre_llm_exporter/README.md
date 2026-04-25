# EPUB to LLM Exporter (Calibre Interface Action Plugin)

This plugin exports selected EPUB books to:

- `<title>.md` (merged markdown)
- `<title>.chunks.jsonl` (LLM-ready chunk records)
- `<title>.meta.json` (book metadata)

## Design highlights

- EPUB parsing from OPF manifest + spine order.
- XHTML to markdown conversion using a vendored pure-Python parser.
- Deterministic, heading-aware, token-bounded chunking.
- Stable chunk IDs for repeatable indexing.

## JSONL schema (per line)

- `id`
- `book_id`
- `title`
- `authors`
- `chapter_idx`
- `chapter_title`
- `section_path`
- `chunk_idx`
- `char_start`, `char_end`
- `token_estimate`
- `text`, `text_plain`
- `has_table`, `has_footnotes`
- `source.epub_href`, `source.anchors`

## Local CLI testing

```bash
python -m calibre_llm_exporter.cli /path/to/book.epub --output-dir ./out --book-id calibre:123
```

## Calibre plugin packaging

Zip the `calibre_llm_exporter` folder as a calibre plugin and install via
`Preferences -> Plugins -> Load plugin from file`.
