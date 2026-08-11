"""Defaults that marketplace HTTP clients rely on."""

from __future__ import annotations

from epicure_mcp.config import load_config


def test_default_allowed_origins_include_cursor_and_claude() -> None:
    cfg = load_config()
    origins = set(cfg.allowed_origins)
    assert "https://claude.ai" in origins
    assert "https://cursor.com" in origins
    assert "https://www.cursor.com" in origins
    assert "https://cursor.sh" in origins
    assert "https://epicure.kaikaku.ai" in origins
