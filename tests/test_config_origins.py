"""Defaults that marketplace HTTP clients rely on."""

from __future__ import annotations

import pytest

from epicure_mcp.config import load_config


def test_default_allowed_origins_include_chatgpt_cursor_and_claude() -> None:
    cfg = load_config()
    origins = set(cfg.allowed_origins)
    assert "https://chatgpt.com" in origins
    assert "https://www.chatgpt.com" in origins
    assert "https://chat.openai.com" in origins
    assert "https://www.chat.openai.com" in origins
    assert "https://claude.ai" in origins
    assert "https://cursor.com" in origins
    assert "https://www.cursor.com" in origins
    assert "https://cursor.sh" in origins
    assert "https://epicure.kaikaku.ai" in origins


def test_explicit_none_ignores_inherited_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_MODE", "none")
    monkeypatch.setenv("MCP_API_TOKEN", "inherited-shared-secret")

    cfg = load_config()

    assert cfg.auth_mode == "none"
    assert cfg.api_token is None


def test_token_without_mode_retains_private_deployment_compatibility(monkeypatch) -> None:
    monkeypatch.delenv("MCP_AUTH_MODE", raising=False)
    monkeypatch.setenv("MCP_API_TOKEN", "legacy-private-secret")

    cfg = load_config()

    assert cfg.auth_mode == "bearer"
    assert cfg.api_token == "legacy-private-secret"


def test_bearer_mode_requires_and_uses_token(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_API_TOKEN", "private-deployment-secret")

    cfg = load_config()

    assert cfg.auth_mode == "bearer"
    assert cfg.api_token == "private-deployment-secret"


def test_bearer_mode_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_MODE", "bearer")
    monkeypatch.delenv("MCP_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="MCP_API_TOKEN is required"):
        load_config()


def test_unknown_auth_mode_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_MODE", "oauth")

    with pytest.raises(ValueError, match="MCP_AUTH_MODE must be one of"):
        load_config()
