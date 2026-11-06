from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/reproducibility.py"
SPEC = importlib.util.spec_from_file_location("epicure_reproducibility", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
reproducibility = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reproducibility)


def test_checked_in_lock_is_exact_sorted_and_hashed() -> None:
    lock = ROOT / "reproducibility/runtime-linux-x86_64-cp312.lock"
    packages = reproducibility.parse_lock(lock)

    assert len(packages) == 41
    assert [package["name"] for package in packages] == sorted(
        package["name"] for package in packages
    )
    assert all(package["sha256"] for package in packages)
    assert {package["name"] for package in packages} >= {
        "mcp",
        "numpy",
        "orjson",
        "pandas",
        "pydantic",
        "starlette",
        "uvicorn",
    }


def test_checked_in_sbom_exactly_matches_lock() -> None:
    lock = ROOT / "reproducibility/runtime-linux-x86_64-cp312.lock"
    sbom = ROOT / "reproducibility/runtime-linux-x86_64-cp312.cdx.json"

    reproducibility.verify_sbom(lock, sbom)
    document = json.loads(sbom.read_text(encoding="utf-8"))
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.5"
    assert len(document["components"]) == 41


def test_runtime_manifest_reproduces_runtime_provenance_identity() -> None:
    lock = ROOT / "reproducibility/runtime-linux-x86_64-cp312.lock"
    sbom = ROOT / "reproducibility/runtime-linux-x86_64-cp312.cdx.json"

    document = reproducibility.build_runtime_manifest(ROOT, lock, sbom)

    assert document["data"]["sha256"] == (
        "98d0403115bf8eb4fb71dbb89a53362e9b9acafda7494c464763df7d764174d1"
    )
    assert document["source"]["sha256"] == (
        "cbf5333f8c20ac961d6390fb5b7c481a9afb882c25725b8517dc5a091cf42b38"
    )
    assert document["data"]["ingredient_count"] == 1790
    assert document["data"]["embedding_dimensions"] == 300
    assert document["boundary"]["training_lineage_recovered"] is False
    assert document["boundary"]["payload_publicly_redistributable"] is False


def test_lock_rejects_unhashed_or_source_distribution_requirements(tmp_path: Path) -> None:
    unhashed = tmp_path / "unhashed.lock"
    unhashed.write_text("--only-binary=:all:\nexample==1.0\n", encoding="utf-8")
    with pytest.raises(reproducibility.ReproducibilityError, match="exactly pinned"):
        reproducibility.parse_lock(unhashed)

    source_allowed = tmp_path / "source-allowed.lock"
    source_allowed.write_text(
        "example==1.0 --hash=sha256:" + "a" * 64 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(reproducibility.ReproducibilityError, match="binary wheels"):
        reproducibility.parse_lock(source_allowed)


def test_wheelhouse_must_exactly_cover_lock_hashes(tmp_path: Path) -> None:
    lock = tmp_path / "fixture.lock"
    wheel = tmp_path / "wheelhouse/example-1.0-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"sealed wheel")
    digest = reproducibility._file_sha256(wheel)
    lock.write_text(
        f"--only-binary=:all:\nexample==1.0 --hash=sha256:{digest}\n",
        encoding="utf-8",
    )

    manifest = reproducibility.wheelhouse_manifest(lock, wheel.parent)
    assert manifest["entries"][0]["sha256"] == digest

    (wheel.parent / "unexpected.whl").write_bytes(b"unexpected")
    with pytest.raises(reproducibility.ReproducibilityError, match="exact lock cover"):
        reproducibility.wheelhouse_manifest(lock, wheel.parent)


def test_content_address_fails_closed_after_mutation() -> None:
    document = reproducibility._with_digest(
        {"schema_version": reproducibility.RECEIPT_SCHEMA, "status": "verified"}
    )
    assert reproducibility.verify_content_addressed(document, reproducibility.RECEIPT_SCHEMA)

    document["status"] = "mutated"
    assert not reproducibility.verify_content_addressed(document, reproducibility.RECEIPT_SCHEMA)
