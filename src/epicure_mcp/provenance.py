"""Content-addressed runtime provenance for the bundled Epicure artefacts.

The data-bundle identity is derived from a canonical manifest containing every
regular file below the configured data directory.  Deployment automation may
provide an immutable application or image digest.  Without one, the server
hashes its installed Python sources and labels that identity as development so
it cannot be confused with a published release.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

PROVENANCE_SCHEMA_VERSION = "epicure-runtime-provenance-v1"
DATA_MANIFEST_VERSION = "epicure-data-bundle-manifest-v1"
SOURCE_MANIFEST_VERSION = "epicure-python-source-manifest-v1"


class ProvenanceError(RuntimeError):
    """Raised when a deterministic provenance identity cannot be produced."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(manifest_version: str, entries: list[dict[str, Any]]) -> str:
    payload = {
        "manifest_version": manifest_version,
        "entries": entries,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _manifest_entries(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise ProvenanceError("manifest root is not a directory")

    entries: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ProvenanceError("manifest inputs must not contain symbolic links")
        if not path.is_file():
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    if not entries:
        raise ProvenanceError("manifest contains no files")
    return entries


def data_bundle_manifest(data_dir: Path) -> tuple[list[dict[str, Any]], str]:
    """Return the canonical data manifest and its content-derived SHA-256."""
    root = data_dir.resolve()
    entries = _manifest_entries(root, root.rglob("*"))
    return entries, _canonical_sha256(DATA_MANIFEST_VERSION, entries)


def source_manifest(source_dir: Path) -> tuple[list[dict[str, Any]], str]:
    """Hash installed Python sources for a development-only application ID."""
    root = source_dir.resolve()
    entries = _manifest_entries(root, root.rglob("*.py"))
    return entries, _canonical_sha256(SOURCE_MANIFEST_VERSION, entries)


def embedding_shape(embeddings_csv: Path) -> tuple[int, int]:
    """Read ingredient count and embedding width without loading the model."""
    try:
        with embeddings_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            dimensions = sum(column.startswith("dim_") for column in header)
            ingredient_count = sum(1 for row in reader if row)
    except (OSError, StopIteration, UnicodeError) as exc:
        raise ProvenanceError("embeddings metadata is unavailable") from exc
    if dimensions <= 0 or ingredient_count <= 0:
        raise ProvenanceError("embeddings metadata is invalid")
    return ingredient_count, dimensions


@lru_cache(maxsize=4)
def build_provenance_payload(
    data_dir: str,
    release_id: str,
    application_sha256: str | None,
    source_dir: str,
) -> dict[str, Any]:
    """Build and cache the immutable runtime provenance response payload."""
    root = Path(data_dir).resolve()
    manifest, bundle_sha256 = data_bundle_manifest(root)
    ingredient_count, dimensions = embedding_shape(root / "embeddings.csv")

    if application_sha256:
        application = {
            "sha256": application_sha256,
            "identity": "configured_immutable_digest",
            "development": False,
            "manifest_version": None,
            "manifest": [],
        }
    else:
        source_entries, source_sha256 = source_manifest(Path(source_dir))
        application = {
            "sha256": source_sha256,
            "identity": "development_source_manifest",
            "development": True,
            "manifest_version": SOURCE_MANIFEST_VERSION,
            "manifest": source_entries,
        }

    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "release_id": release_id,
        "bundle_sha256": bundle_sha256,
        "application_sha256": application["sha256"],
        "ingredient_count": ingredient_count,
        "embedding_dimensions": dimensions,
        "bundle": {
            "manifest_version": DATA_MANIFEST_VERSION,
            "manifest": manifest,
        },
        "application": application,
        "notice": (
            "This identity describes the exact runtime artefacts. It does not identify "
            "the exploratory unmatched bundle as a public Cooc, Core, or Chem release."
        ),
    }
