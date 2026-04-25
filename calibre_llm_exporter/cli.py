from __future__ import annotations

import argparse
import json

from .converter import export_epub_for_llm


def main() -> int:
  parser = argparse.ArgumentParser(description='Export EPUB into Markdown + LLM JSONL chunks')
  parser.add_argument('epub', help='Path to EPUB file')
  parser.add_argument('--output-dir', required=True, help='Output directory')
  parser.add_argument('--book-id', default='local:epub', help='Book identifier')
  args = parser.parse_args()

  files = export_epub_for_llm(args.epub, args.output_dir, book_id=args.book_id)
  print(json.dumps(files, ensure_ascii=False, indent=2))
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
