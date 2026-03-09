# CHANGELOG

All notable changes to claude-brain.

---

## [0.1.0] — 2026-03-09

### Added
- **Bash-to-Python migration complete** — all hooks and scripts are now pure Python. No bash dependencies. Cross-platform ready (Linux, macOS; Windows via WSL).
- **Batch embedding backfill** — `scripts/batch_embed.py` backfills semantic search vectors for all existing transcripts.
- **requirements.txt** — standard Python dependency file for pip install.
- **Email digest framework** — architecture supports scheduled email summaries (daily recaps, weekly progress, dormant project alerts).

### Changed
- All 4 hooks rewritten from bash to Python (`hooks/*.py`).
- All support scripts rewritten from bash to Python (`scripts/brain_sync.py`, `scripts/startup_check.py`).
- Documentation rewritten for public release (README.md, CLAUDE_BRAIN_HOW_TO.md).
- Project prefix standard set to 2-3 characters (was 2-4).
- Brain health check now achieves 9/9 PASS (embedding coverage at 100%).

### Removed
- All `.sh` shell scripts (replaced by `.py` equivalents).
- Internal/personal references from public-facing documentation.

---

## [0.0.1] — 2026-02-01

### Added
- Initial implementation — SQLite database, 4 lifecycle hooks (bash), MCP server with 11 tools.
- 11 slash commands (`/brain-question`, `/brain-search`, `/brain-history`, `/brain-recap`, `/brain-decide`, `/brain-health`, `/brain-status`, `/brain-import`, `/brain-questionnaire`, `/brain-setup`, `/brain-export`).
- Dual search: FTS5 keyword search + semantic search (sentence-transformers + numpy).
- Session quality scoring and tagging.
- Claude.ai conversation import via Chrome extension export.
- Interactive setup wizard (`brain-setup.py`).
- Multi-machine support via Dropbox/cloud sync.
- LLM-powered session summaries via direct API call (OpenRouter/Anthropic).
