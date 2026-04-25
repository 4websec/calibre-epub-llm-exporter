from __future__ import annotations

import traceback
from pathlib import Path

from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction

from .converter import export_epub_for_llm


class EpubToLlmExporterAction(InterfaceAction):
  name = 'EPUB to LLM Exporter'
  action_spec = (
    'EPUB → LLM export',
    None,
    'Export selected EPUB books to Markdown + JSONL chunks',
    None,
  )

  def genesis(self):
    self.qaction.triggered.connect(self.export_selected)

  def export_selected(self):
    db = self.gui.current_db.new_api
    selected_ids = list(self.gui.library_view.get_selected_ids())

    if not selected_ids:
      info_dialog(self.gui, 'EPUB → LLM export', 'No books selected.', show=True)
      return

    successes: list[str] = []
    failures: list[str] = []

    for book_id in selected_ids:
      try:
        epub_path = db.format_abspath(book_id, 'EPUB', index_is_id=True)
        if not epub_path:
          failures.append(f'Book {book_id}: no EPUB format found')
          continue

        title = db.field_for('title', book_id) or f'book-{book_id}'
        output_dir = str(Path(epub_path).with_suffix(''))
        files = export_epub_for_llm(epub_path, output_dir, book_id=f'calibre:{book_id}')
        successes.append(f'{title} → {files["jsonl"]}')
      except Exception as exc:  # noqa: BLE001 - plugin boundary should never crash GUI
        failures.append(f'Book {book_id}: {exc}')

    if failures:
      details = '\n'.join(failures) + '\n\n' + traceback.format_exc()
      error_dialog(
        self.gui,
        'EPUB → LLM export',
        f'Completed with {len(failures)} errors and {len(successes)} successes.',
        det_msg=details,
        show=True,
      )
      return

    info_dialog(
      self.gui,
      'EPUB → LLM export',
      f'Exported {len(successes)} book(s).\n\n' + '\n'.join(successes[:15]),
      show=True,
    )
