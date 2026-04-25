try:
  from calibre.customize import InterfaceActionBase
except ModuleNotFoundError:  # pragma: no cover - for local tests without calibre
  class InterfaceActionBase:  # type: ignore[override]
    pass


class EpubToLlmExporterPlugin(InterfaceActionBase):
  name = 'EPUB to LLM Exporter'
  description = 'Export EPUB books to Markdown and LLM-ready JSONL chunks.'
  supported_platforms = ['windows', 'osx', 'linux']
  author = 'Codex'
  version = (0, 1, 0)
  minimum_calibre_version = (7, 0, 0)
  actual_plugin = 'calibre_plugins.epub_to_llm_exporter.action:EpubToLlmExporterAction'
