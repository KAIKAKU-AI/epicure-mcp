from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from epicure_mcp.config import DEFAULT_EXPLORATORY_RELEASE_ID, load_config
from epicure_mcp.provenance import (
    DATA_MANIFEST_VERSION,
    SOURCE_MANIFEST_VERSION,
    build_provenance_payload,
    data_bundle_manifest,
    source_manifest,
)
from epicure_mcp.server import build_app


def _write_test_bundle(root: Path, *, metadata_first: bool = False) -> None:
    root.mkdir()
    embeddings = "node_id,name,dim_0,dim_1\n1,tomato,0.1,0.2\n2,basil,0.3,0.4\n"
    metadata = json.dumps({"representation": "exploratory-unmatched"}, sort_keys=True)
    files = [
        (root / "embeddings.csv", embeddings),
        (root / "metadata.json", metadata),
    ]
    if metadata_first:
        files.reverse()
    for path, content in files:
        path.write_text(content, encoding="utf-8")


def test_bundle_and_source_manifests_are_canonical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_test_bundle(first)
    _write_test_bundle(second, metadata_first=True)

    first_entries, first_hash = data_bundle_manifest(first)
    second_entries, second_hash = data_bundle_manifest(second)
    assert first_entries == second_entries
    assert first_hash == second_hash
    assert [entry["path"] for entry in first_entries] == ["embeddings.csv", "metadata.json"]
    assert all(len(entry["sha256"]) == 64 for entry in first_entries)

    (second / "metadata.json").write_text('{"representation":"changed"}', encoding="utf-8")
    _, changed_hash = data_bundle_manifest(second)
    assert changed_hash != first_hash

    source = tmp_path / "source"
    (source / "tools").mkdir(parents=True)
    (source / "server.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "tools" / "pairing.py").write_text("def run(): return 1\n", encoding="utf-8")
    (source / "README.txt").write_text("not executable source", encoding="utf-8")
    source_entries, source_hash = source_manifest(source)
    assert [entry["path"] for entry in source_entries] == ["server.py", "tools/pairing.py"]
    assert len(source_hash) == 64


def test_development_and_configured_application_identities(tmp_path: Path) -> None:
    data = tmp_path / "data"
    source = tmp_path / "source"
    _write_test_bundle(data)
    source.mkdir()
    (source / "app.py").write_text("VERSION = 'development'\n", encoding="utf-8")
    build_provenance_payload.cache_clear()

    development = build_provenance_payload(
        str(data),
        "exploratory-unmatched-test",
        None,
        str(source),
    )
    assert development["release_id"] == "exploratory-unmatched-test"
    assert development["ingredient_count"] == 2
    assert development["embedding_dimensions"] == 2
    assert development["bundle"]["manifest_version"] == DATA_MANIFEST_VERSION
    assert development["application"]["identity"] == "development_source_manifest"
    assert development["application"]["development"] is True
    assert development["application"]["manifest_version"] == SOURCE_MANIFEST_VERSION
    assert development["application_sha256"] == development["application"]["sha256"]
    assert "public Cooc, Core, or Chem release" in development["notice"]

    configured_sha = "a" * 64
    configured = build_provenance_payload(
        str(data),
        "private-exploratory-build",
        configured_sha,
        str(source),
    )
    assert configured["application_sha256"] == configured_sha
    assert configured["application"] == {
        "sha256": configured_sha,
        "identity": "configured_immutable_digest",
        "development": False,
        "manifest_version": None,
        "manifest": [],
    }


def test_provenance_configuration_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EPICURE_RELEASE_ID", raising=False)
    monkeypatch.delenv("EPICURE_APPLICATION_SHA256", raising=False)
    default = load_config()
    assert default.release_id == DEFAULT_EXPLORATORY_RELEASE_ID
    assert "exploratory-unmatched" in default.release_id
    assert default.application_sha256 is None

    monkeypatch.setenv("EPICURE_RELEASE_ID", "exploratory-unmatched-ci")
    monkeypatch.setenv("EPICURE_APPLICATION_SHA256", "B" * 64)
    configured = load_config()
    assert configured.release_id == "exploratory-unmatched-ci"
    assert configured.application_sha256 == "b" * 64

    monkeypatch.setenv("EPICURE_APPLICATION_SHA256", "not-a-sha")
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        load_config()


@pytest.mark.anyio
async def test_provenance_endpoint_is_get_only_and_bearer_protected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = tmp_path / "endpoint-data"
    _write_test_bundle(data)
    monkeypatch.setenv("EPICURE_DATA_DIR", str(data))
    monkeypatch.setenv("EPICURE_RELEASE_ID", "exploratory-unmatched-endpoint-test")
    monkeypatch.setenv("EPICURE_APPLICATION_SHA256", "c" * 64)
    monkeypatch.setenv("MCP_API_TOKEN", "provenance-test-token")
    build_provenance_payload.cache_clear()

    app = build_app()
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            missing = await client.get("/provenance")
            assert missing.status_code == 401
            assert missing.headers["www-authenticate"] == "Bearer"

            headers = {"Authorization": "Bearer provenance-test-token"}
            response = await client.get("/provenance", headers=headers)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            payload = response.json()
            assert payload["release_id"] == "exploratory-unmatched-endpoint-test"
            assert payload["bundle_sha256"]
            assert payload["application_sha256"] == "c" * 64
            assert payload["ingredient_count"] == 2
            assert payload["embedding_dimensions"] == 2
            assert len(payload["bundle"]["manifest"]) == 2

            method_not_allowed = await client.post("/provenance", headers=headers)
            assert method_not_allowed.status_code == 405
