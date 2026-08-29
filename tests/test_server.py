"""End-to-end server test: spin up the ASGI app and invoke an MCP tool via
the Streamable HTTP transport."""

from __future__ import annotations

import json

import httpx
import pytest
from asgi_lifespan import LifespanManager

from epicure_mcp.server import build_app

pytestmark = pytest.mark.usefixtures("use_real_bundle")

JSONRPC_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

EXPECTED_TOOL_TITLES = {
    "compare_on_axis": "Compare ingredients on an axis",
    "pairing_score": "Score an ingredient pairing",
    "find_pairings": "Explore ingredient pairings",
    "flavour_correlations": "Inspect flavour correlations",
    "cultural_profile": "Profile an ingredient by cuisine",
    "neighbors": "Find similar ingredients",
    "morph": "Transform an ingredient in flavour space",
    "list_targets": "List transformation targets",
    "list_factors": "List flavour factors",
    "ingredient_on_factor": "Project an ingredient onto a factor",
    "pareto_navigate": "Navigate a flavour trade-off",
    "closest_mode": "Find an ingredient's flavour region",
    "where_on_atlas": "Locate an ingredient on the atlas",
}


def _decode(text: str) -> dict:
    """Decode an SSE or plain-JSON MCP response."""
    if text.startswith("event:") or "\ndata:" in text or text.startswith("data:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return json.loads(text)


@pytest.mark.anyio
async def test_healthz_and_initialize() -> None:
    app = build_app()
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        await _run_session(transport)


@pytest.mark.anyio
async def test_bearer_authentication(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_API_TOKEN", "test-mcp-bearer-token")
    app = build_app()
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            assert (await client.get("/healthz")).status_code == 200
            assert (await client.get("/atlas")).status_code == 401

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.1"},
                },
            }
            missing = await client.post("/mcp", json=payload, headers=JSONRPC_HEADERS)
            assert missing.status_code == 401
            assert missing.headers["www-authenticate"] == "Bearer"

            invalid = await client.post(
                "/mcp",
                json=payload,
                headers={**JSONRPC_HEADERS, "Authorization": "Bearer wrong"},
            )
            assert invalid.status_code == 401

            valid = await client.post(
                "/mcp",
                json=payload,
                headers={
                    **JSONRPC_HEADERS,
                    "Authorization": "Bearer test-mcp-bearer-token",
                },
            )
            assert valid.status_code == 200
            assert "result" in _decode(valid.text)

            atlas = await client.get(
                "/atlas",
                headers={"Authorization": "Bearer test-mcp-bearer-token"},
            )
            assert atlas.status_code == 200
            assert atlas.json()["dimensions"] == 3


@pytest.mark.anyio
async def test_explicit_public_mode_accepts_chatgpt_with_inherited_token(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_MODE", "none")
    monkeypatch.setenv("MCP_API_TOKEN", "inherited-shared-secret")
    app = build_app()
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            response = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "0.1"},
                    },
                },
                headers={**JSONRPC_HEADERS, "Origin": "https://chatgpt.com"},
            )

            assert response.status_code == 200
            assert "www-authenticate" not in response.headers
            assert "result" in _decode(response.text)


async def _run_session(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost", follow_redirects=True
    ) as client:
        health = await client.get("/healthz")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["referrer-policy"] == "no-referrer"
        assert "max-age=63072000" in health.headers["strict-transport-security"]

        atlas = await client.get("/atlas")
        assert atlas.status_code == 200
        atlas_body = atlas.json()
        assert atlas_body["dimensions"] == 3
        assert atlas_body["total"] == 1790
        assert len(atlas_body["points"]) == 1790
        assert {"name", "x", "y", "z", "group"} <= atlas_body["points"][0].keys()
        assert "max-age=86400" in atlas.headers["cache-control"]

        # Favicon endpoints should serve the PNG bytes with the right
        # content-type so browser unfurlers / link previews work.
        favicon_ico = await client.get("/favicon.ico")
        assert favicon_ico.status_code == 200
        assert favicon_ico.headers["content-type"] == "image/png"
        assert favicon_ico.content[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic
        favicon_png = await client.get("/favicon.png")
        assert favicon_png.status_code == 200
        assert favicon_png.content == favicon_ico.content

        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0.1"},
            },
        }
        resp = await client.post("/mcp", json=init_payload, headers=JSONRPC_HEADERS)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-store"
        body = _decode(resp.text)
        assert body["jsonrpc"] == "2.0"
        assert "result" in body
        # MCP server should advertise its icon in serverInfo.icons.
        server_info = body["result"].get("serverInfo") or {}
        assert server_info["name"] == "Epicure"
        assert server_info["websiteUrl"] == "https://epicure.kaikaku.ai/agents"
        icons = server_info.get("icons") or []
        assert icons, "initialize should advertise at least one icon"
        assert icons[0]["mimeType"] == "image/png"
        assert icons[0]["src"].startswith("data:image/png;base64,")
        session_id = resp.headers.get("mcp-session-id")
        assert session_id

        await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={**JSONRPC_HEADERS, "mcp-session-id": session_id},
        )

        list_resp = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers={**JSONRPC_HEADERS, "mcp-session-id": session_id},
        )
        assert list_resp.status_code == 200
        list_body = _decode(list_resp.text)
        tools = list_body["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        for required in (
            "compare_on_axis",
            "pairing_score",
            "find_pairings",
            "flavour_correlations",
            "cultural_profile",
            "neighbors",
            "morph",
            "list_targets",
            "list_factors",
            "ingredient_on_factor",
            "pareto_navigate",
            "closest_mode",
            "where_on_atlas",
        ):
            assert required in tool_names, f"missing tool: {required}"

        assert tool_names == set(EXPECTED_TOOL_TITLES)
        for tool in tools:
            annotations = tool.get("annotations") or {}
            assert tool.get("title") == EXPECTED_TOOL_TITLES[tool["name"]]
            assert annotations.get("title") == EXPECTED_TOOL_TITLES[tool["name"]]
            assert annotations.get("readOnlyHint") is True
            assert annotations.get("destructiveHint") is False
            assert annotations.get("idempotentHint") is True
            assert annotations.get("openWorldHint") is False
            metadata = tool.get("_meta") or {}
            assert metadata.get("securitySchemes") == [{"type": "noauth"}]
            description = tool.get("description", "")
            assert description
            for coercive_phrase in ("MANDATORY", "MUST", "ALWAYS", "NEVER", "Do NOT"):
                assert coercive_phrase not in description

        # The morph.target parameter must surface as a discriminated union
        # so MCP clients can validate their payload before invoking.
        morph_tool = next(t for t in list_body["result"]["tools"] if t["name"] == "morph")
        target_schema = morph_tool["inputSchema"]["properties"]["target"]
        branches = target_schema.get("oneOf") or target_schema.get("anyOf")
        assert branches is not None, f"morph.target should be a union; got: {target_schema}"
        # Resolve $ref-style branches against the schema's $defs so we can
        # inspect their `kind` discriminator.
        defs = morph_tool["inputSchema"].get("$defs") or morph_tool["inputSchema"].get(
            "definitions", {}
        )

        def _resolve(branch: dict) -> dict:
            ref = branch.get("$ref")
            if not ref:
                return branch
            return defs.get(ref.rsplit("/", 1)[-1], branch)

        kinds: set[str] = set()
        for branch in branches:
            resolved = _resolve(branch)
            kind_prop = resolved.get("properties", {}).get("kind", {})
            const = kind_prop.get("const")
            enum = kind_prop.get("enum")
            if const:
                kinds.add(const)
            elif enum:
                kinds.update(enum)
        assert kinds == {"direction", "mode", "ingredient"}, (
            f"morph.target must discriminate on kind in {{'direction', 'mode', "
            f"'ingredient'}}; got {kinds}"
        )

        call_resp = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "pairing_score",
                    "arguments": {"ingredient_a": "miso", "ingredient_b": "soy_sauce"},
                },
            },
            headers={**JSONRPC_HEADERS, "mcp-session-id": session_id},
        )
        assert call_resp.status_code == 200
        call_body = _decode(call_resp.text)
        result = call_body["result"]
        text_block = next(
            (b["text"] for b in result.get("content", []) if b.get("type") == "text"), None
        )
        assert text_block is not None
        payload = json.loads(text_block)
        assert payload["resolved_a"] == "miso"
        assert -1.0 <= payload["pairing_score"] <= 1.0

        unknown_resp = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "pairing_score",
                    "arguments": {
                        "ingredient_a": "zzz_unknown_ingredient",
                        "ingredient_b": "miso",
                    },
                },
            },
            headers={**JSONRPC_HEADERS, "mcp-session-id": session_id},
        )
        unknown_result = _decode(unknown_resp.text)["result"]
        assert unknown_result["isError"] is True

        invalid_resp = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "list_targets",
                    "arguments": {"kind": "not-a-valid-kind"},
                },
            },
            headers={**JSONRPC_HEADERS, "mcp-session-id": session_id},
        )
        invalid_result = _decode(invalid_resp.text)["result"]
        assert invalid_result["isError"] is True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
