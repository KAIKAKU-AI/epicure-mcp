# Changelog

## 1.0.0 — 2026-08-11

### Added

- Cursor Marketplace plugin package: `.cursor-plugin/plugin.json`, `mcp.json`,
  skills, rules, commands, agents, and `assets/logo.svg`.
- `docs/CURSOR_MARKETPLACE_SUBMISSION.md` listing copy and live portal checklist
  (publisher application fields captured from cursor.com/marketplace/publish).
- `scripts/validate_plugin.py` local marketplace scaffolding validator.
- Default `MCP_ALLOWED_ORIGINS` entries for Cursor (`cursor.com` / `cursor.sh`).

### Notes

- Public MCP endpoint remains `https://epicure-mcp.kaikaku.ai/mcp` (no auth);
  `mcp.json` uses `"type": "http"`.
- Production must redeploy for the Cursor origin allowlist to take effect.
- Marketplace publish form draft can be prepared before push; do not click
  **Submit Application** until packaging is on public `main`.
