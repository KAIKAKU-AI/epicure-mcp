"""Build and verify fail-closed Epicure runtime reproducibility evidence.

This module deliberately separates runtime reconstruction from model lineage.
It can prove that the checked-out Python sources, bundled data, and locked
runtime dependencies execute together. It cannot recover the embedding
training run, confer data rights, publish the private payload, or manufacture
an OCI digest when no container daemon is available.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

DATA_MANIFEST_VERSION = "epicure-data-bundle-manifest-v1"
SOURCE_MANIFEST_VERSION = "epicure-python-source-manifest-v1"
RUNTIME_MANIFEST_SCHEMA = "epicure-exact-runtime-manifest-v1"
RECEIPT_SCHEMA = "epicure-private-offline-rebuild-receipt-v1"
SBOM_SPEC_VERSION = "1.5"
LOCK_TARGET = "CPython 3.12 / Linux x86_64 / manylinux-compatible glibc"

_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)\s+(.*)$")
_HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})(?:\s|$)")


class ReproducibilityError(RuntimeError):
    """The supplied reconstruction evidence is incomplete or inconsistent."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(path: Path) -> list[dict[str, Any]]:
    """Parse a binary-only, exact-pin, SHA-256 requirements lock."""

    if path.is_symlink() or not path.is_file():
        raise ReproducibilityError("dependency lock must be a regular file")
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    logical: list[str] = []
    pending = ""
    binary_only = False
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "--only-binary=:all:":
            if pending:
                raise ReproducibilityError("binary-only option interrupts a requirement")
            binary_only = True
            continue
        pending = f"{pending} {stripped}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        logical.append(pending)
        pending = ""
    if pending:
        raise ReproducibilityError("dependency lock ends with an incomplete requirement")
    if not binary_only:
        raise ReproducibilityError("dependency lock must require binary wheels")

    packages: list[dict[str, Any]] = []
    names: set[str] = set()
    for line in logical:
        match = _PIN.fullmatch(line)
        if not match:
            raise ReproducibilityError(f"dependency is not exactly pinned: {line}")
        name = _normalise_name(match.group(1))
        if name in names:
            raise ReproducibilityError(f"duplicate dependency: {name}")
        hashes = sorted(set(_HASH.findall(match.group(3))))
        residue = _HASH.sub("", match.group(3)).strip()
        if not hashes or residue:
            raise ReproducibilityError(f"dependency is not exclusively SHA-256 locked: {name}")
        packages.append({"name": name, "version": match.group(2), "sha256": hashes})
        names.add(name)
    if not packages:
        raise ReproducibilityError("dependency lock is empty")
    if [item["name"] for item in packages] != sorted(names):
        raise ReproducibilityError("dependency lock must be sorted by normalized package name")
    return packages


def build_sbom(lock_path: Path) -> dict[str, Any]:
    """Return a deterministic CycloneDX SBOM for the selected runtime wheels."""

    packages = parse_lock(lock_path)
    components: list[dict[str, Any]] = []
    for package in packages:
        name = package["name"]
        version = package["version"]
        components.append(
            {
                "bom-ref": f"pkg:pypi/{name}@{version}",
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
                "hashes": [{"alg": "SHA-256", "content": digest} for digest in package["sha256"]],
                "scope": "required",
                "properties": [
                    {
                        "name": "epicure:hash-subject",
                        "value": "selected distribution wheel",
                    }
                ],
            }
        )
    direct = [
        "mcp",
        "numpy",
        "orjson",
        "pandas",
        "pydantic",
        "starlette",
        "uvicorn",
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": SBOM_SPEC_VERSION,
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": "pkg:pypi/epicure-mcp@1.0.0",
                "type": "application",
                "name": "epicure-mcp",
                "version": "1.0.0",
                "purl": "pkg:pypi/epicure-mcp@1.0.0",
            },
            "properties": [
                {"name": "epicure:lock-sha256", "value": _file_sha256(lock_path)},
                {"name": "epicure:target", "value": LOCK_TARGET},
                {
                    "name": "epicure:scope",
                    "value": (
                        "runtime dependencies; project source and data are separately manifested"
                    ),
                },
            ],
        },
        "components": components,
        "dependencies": [
            {
                "ref": "pkg:pypi/epicure-mcp@1.0.0",
                "dependsOn": [
                    next(
                        component["bom-ref"]
                        for component in components
                        if component["name"] == name
                    )
                    for name in direct
                ],
            }
        ],
    }


def _manifest(root: Path, paths: Sequence[Path], version: str) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise ReproducibilityError(f"manifest root must be a regular directory: {root}")
    entries: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ReproducibilityError(f"manifest input is a symbolic link: {path}")
        if path.is_file():
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _file_sha256(path),
                }
            )
    if not entries:
        raise ReproducibilityError(f"{version} contains no files")
    return {
        "manifest_version": version,
        "entries": entries,
        "sha256": _canonical_sha256({"manifest_version": version, "entries": entries}),
    }


def _embedding_shape(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        dimensions = sum(column.startswith("dim_") for column in header)
        ingredients = sum(1 for row in reader if row)
    if ingredients <= 0 or dimensions <= 0:
        raise ReproducibilityError("embeddings.csv has an invalid shape")
    return ingredients, dimensions


def build_runtime_manifest(root: Path, lock_path: Path, sbom_path: Path) -> dict[str, Any]:
    """Bind the exact source, data, dependency lock, and SBOM inputs."""

    root = root.resolve()
    source_root = root / "src/epicure_mcp"
    data_root = root / "data"
    source = _manifest(source_root, tuple(source_root.rglob("*.py")), SOURCE_MANIFEST_VERSION)
    data = _manifest(data_root, tuple(data_root.rglob("*")), DATA_MANIFEST_VERSION)
    ingredient_count, dimensions = _embedding_shape(data_root / "embeddings.csv")
    return {
        "schema_version": RUNTIME_MANIFEST_SCHEMA,
        "record_role": "exact_private_runtime_reconstruction_inputs",
        "release_id": "exploratory-unmatched-1790-runtime",
        "runtime_id": (
            f"epicure-mcp-1790-r1+bundle.{data['sha256'][:12]}.app.{source['sha256'][:12]}"
        ),
        "data": {
            **data,
            "ingredient_count": ingredient_count,
            "embedding_dimensions": dimensions,
        },
        "source": source,
        "dependency_lock": {
            "path": lock_path.resolve().relative_to(root).as_posix(),
            "sha256": _file_sha256(lock_path),
            "package_count": len(parse_lock(lock_path)),
            "target": LOCK_TARGET,
        },
        "sbom": {
            "path": sbom_path.resolve().relative_to(root).as_posix(),
            "sha256": _file_sha256(sbom_path),
            "format": "CycloneDX 1.5 JSON",
        },
        "boundary": {
            "payload_publicly_redistributable": False,
            "training_lineage_recovered": False,
            "independent_reproduction": False,
            "immutable_oci_digest": None,
        },
    }


def _with_digest(document: Mapping[str, Any]) -> dict[str, Any]:
    unhashed = {key: value for key, value in document.items() if key != "artifact_sha256"}
    return {**unhashed, "artifact_sha256": _canonical_sha256(unhashed)}


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    rendered = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    path.chmod(0o644)


def write_content_addressed(output_dir: Path, stem: str, payload: Mapping[str, Any]) -> Path:
    document = _with_digest(payload)
    path = output_dir / f"{stem}-{document['artifact_sha256']}.json"
    _write_json(path, document)
    return path


def verify_content_addressed(document: object, schema: str) -> bool:
    if not isinstance(document, Mapping) or document.get("schema_version") != schema:
        return False
    digest = document.get("artifact_sha256")
    unhashed = {key: value for key, value in document.items() if key != "artifact_sha256"}
    return isinstance(digest, str) and digest == _canonical_sha256(unhashed)


def verify_sbom(lock_path: Path, sbom_path: Path) -> None:
    expected = build_sbom(lock_path)
    try:
        observed = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReproducibilityError("SBOM is missing or invalid JSON") from error
    if observed != expected:
        raise ReproducibilityError("SBOM does not exactly match the dependency lock")


def wheelhouse_manifest(lock_path: Path, wheelhouse: Path) -> dict[str, Any]:
    """Verify a private wheelhouse is an exact hash cover for the lock."""

    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ReproducibilityError("wheelhouse must be a regular directory")
    expected = {digest for package in parse_lock(lock_path) for digest in package["sha256"]}
    entries = []
    for path in sorted(wheelhouse.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file():
            raise ReproducibilityError("wheelhouse must contain only regular files")
        digest = _file_sha256(path)
        entries.append({"filename": path.name, "bytes": path.stat().st_size, "sha256": digest})
    observed = {entry["sha256"] for entry in entries}
    if observed != expected or len(entries) != len(expected):
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ReproducibilityError(
            f"wheelhouse is not an exact lock cover (missing={missing}, extra={extra})"
        )
    return {
        "manifest_version": "epicure-private-wheelhouse-manifest-v1",
        "entries": entries,
        "sha256": _canonical_sha256(
            {
                "manifest_version": "epicure-private-wheelhouse-manifest-v1",
                "entries": entries,
            }
        ),
    }


def _run(command: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> str:
    process = subprocess.run(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        tail = (process.stderr or process.stdout)[-2000:]
        raise ReproducibilityError(f"command failed ({command[0]}): {tail}")
    return process.stdout.strip()


def _docker_state() -> dict[str, Any]:
    client = subprocess.run(
        ["docker", "version", "--format", "{{json .Client}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    server = subprocess.run(
        ["docker", "version", "--format", "{{json .Server}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    client_value: dict[str, Any] | None = None
    if client.stdout.strip():
        parsed = json.loads(client.stdout)
        if isinstance(parsed, dict):
            client_value = parsed
    daemon_accessible = server.returncode == 0 and server.stdout.strip() not in {"", "null"}
    return {
        "client_available": client_value is not None,
        "client_version": client_value.get("Version") if client_value else None,
        "daemon_accessible": daemon_accessible,
        "daemon_probe_status": (
            "accessible" if daemon_accessible else "unavailable_or_permission_denied"
        ),
        "image_built": False,
        "immutable_oci_digest": None,
    }


def _installed_packages(python: Path, root: Path) -> dict[str, str]:
    output = _run(
        [str(python), "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
        cwd=root,
    )
    values = json.loads(output)
    return {_normalise_name(item["name"]): item["version"] for item in values}


def distribution_integrity(lock_path: Path) -> dict[str, Any]:
    """Verify installed distribution files against RECORD and bind their bytes."""

    packages = parse_lock(lock_path)
    distributions: list[dict[str, Any]] = []
    runtime_payloads: list[dict[str, Any]] = []
    for package in packages:
        try:
            distribution = importlib.metadata.distribution(package["name"])
        except importlib.metadata.PackageNotFoundError as error:
            raise ReproducibilityError(
                f"locked dependency is not installed: {package['name']}"
            ) from error
        if distribution.version != package["version"]:
            raise ReproducibilityError(f"installed version differs from lock: {package['name']}")
        entries: list[dict[str, Any]] = []
        unhashed_paths: list[str] = []
        record_verified = 0
        unhashed = 0
        installation_specific = 0
        for item in sorted(distribution.files or (), key=lambda value: str(value)):
            path = Path(distribution.locate_file(item))
            if path.is_symlink() or not path.is_file():
                raise ReproducibilityError(
                    f"installed distribution file is missing or symbolic: {package['name']}:{item}"
                )
            digest = _file_sha256(path)
            declared = item.hash
            if declared is not None:
                if declared.mode != "sha256":
                    raise ReproducibilityError(
                        f"unsupported RECORD hash for {package['name']}:{item}"
                    )
                observed = base64.urlsafe_b64encode(bytes.fromhex(digest)).decode().rstrip("=")
                if observed != declared.value:
                    raise ReproducibilityError(
                        f"installed file differs from RECORD: {package['name']}:{item}"
                    )
                record_verified += 1
            else:
                unhashed += 1
                unhashed_paths.append(str(item).replace(os.sep, "/"))
                continue
            relative = str(item).replace(os.sep, "/")
            if relative.startswith("../") or ".dist-info/" in relative:
                installation_specific += 1
                continue
            entries.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                }
            )
        runtime_payload = {
            "name": package["name"],
            "version": distribution.version,
            "file_count": len(entries),
            "bytes": sum(entry["bytes"] for entry in entries),
            "physical_files_manifest_sha256": _canonical_sha256(entries),
        }
        runtime_payloads.append(runtime_payload)
        distributions.append(
            {
                **runtime_payload,
                "record_entry_count": len(entries) + installation_specific + unhashed,
                "physically_verified_file_count": len(entries),
                "record_verified_file_count": record_verified,
                "installation_specific_verified_file_count": installation_specific,
                "unhashed_record_file_count": unhashed,
                "unhashed_record_paths_sha256": _canonical_sha256(unhashed_paths),
            }
        )
    return {
        "schema_version": "epicure-installed-distribution-integrity-v1",
        "package_count": len(distributions),
        "all_versions_match_lock": True,
        "all_declared_record_hashes_match_physical_files": True,
        "distributions": distributions,
        "environment_sha256": _canonical_sha256(distributions),
        "runtime_payload_environment_sha256": _canonical_sha256(runtime_payloads),
    }


def _installed_integrity(python: Path, root: Path, lock_path: Path) -> dict[str, Any]:
    output = _run(
        [
            str(python),
            str(Path(__file__).resolve()),
            "inspect-installed",
            "--lock",
            str(lock_path.resolve()),
        ],
        cwd=root,
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ReproducibilityError("installed-distribution probe returned no object")
    return value


def verify_private_offline_rebuild(
    *,
    root: Path,
    lock_path: Path,
    sbom_path: Path,
    wheelhouse: Path,
    base_python: Path,
) -> dict[str, Any]:
    """Install the sealed wheelhouse with no index and probe source plus data."""

    verify_sbom(lock_path, sbom_path)
    wheels = wheelhouse_manifest(lock_path, wheelhouse)
    root = root.resolve()
    packages = parse_lock(lock_path)
    observed_integrity = _installed_integrity(base_python, root, lock_path)
    with tempfile.TemporaryDirectory(prefix="epicure-offline-rebuild-") as temporary:
        rebuild = Path(temporary)
        _run([str(base_python), "-m", "venv", str(rebuild / "venv")], cwd=root)
        python = rebuild / "venv/bin/python"
        offline_env = {
            **os.environ,
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse.resolve()),
                "--require-hashes",
                "-r",
                str(lock_path.resolve()),
            ],
            cwd=root,
            env=offline_env,
        )
        installed = _installed_packages(python, root)
        mismatch = {
            package["name"]: {
                "expected": package["version"],
                "observed": installed.get(package["name"]),
            }
            for package in packages
            if installed.get(package["name"]) != package["version"]
        }
        if mismatch:
            raise ReproducibilityError(f"offline environment differs from lock: {mismatch}")
        rebuilt_integrity = _installed_integrity(python, root, lock_path)
        if (
            rebuilt_integrity["runtime_payload_environment_sha256"]
            != observed_integrity["runtime_payload_environment_sha256"]
        ):
            raise ReproducibilityError(
                "offline reinstall runtime payloads differ from the observed environment"
            )
        _run([str(python), "scripts/verify_data.py", "--data-dir", "data"], cwd=root)
        probe_env = {
            **offline_env,
            "PYTHONPATH": str((root / "src").resolve()),
        }
        probe = json.loads(
            _run(
                [
                    str(python),
                    str(Path(__file__).resolve()),
                    "probe",
                    "--root",
                    str(root),
                ],
                cwd=root,
                env=probe_env,
            )
        )
    expected_manifest = build_runtime_manifest(root, lock_path, sbom_path)
    if probe["bundle_sha256"] != expected_manifest["data"]["sha256"]:
        raise ReproducibilityError("offline probe produced a different data-bundle identity")
    if probe["application_sha256"] != expected_manifest["source"]["sha256"]:
        raise ReproducibilityError("offline probe produced a different source identity")
    return {
        "status": "verified_private_offline_runtime_rebuild",
        "wheelhouse": wheels,
        "dependency_install": {
            "network_mode": "pip --no-index with a sealed private wheelhouse",
            "hash_enforcement": "pip --require-hashes",
            "package_count": len(packages),
            "all_locked_versions_matched": True,
            "physical_runtime_payload_manifests_match_observed_environment": True,
        },
        "observed_runtime_environment": {
            "status": "locked_local_environment_observation",
            "process_binding": (
                "The local venv was used for the loopback runtime, but /provenance does not "
                "attest dependency versions."
            ),
            "integrity": observed_integrity,
        },
        "rebuilt_runtime_environment": {"integrity": rebuilt_integrity},
        "data_verification": {"passed": True, "script": "scripts/verify_data.py"},
        "runtime_probe": {**probe, "passed": True},
        "independent_operator": False,
        "public_payload_used": False,
    }


def build_receipt(
    *,
    root: Path,
    lock_path: Path,
    sbom_path: Path,
    wheelhouse: Path,
    base_python: Path,
    recovered_inventory_path: Path | None,
) -> dict[str, Any]:
    manifest = build_runtime_manifest(root, lock_path, sbom_path)
    rebuild = verify_private_offline_rebuild(
        root=root,
        lock_path=lock_path,
        sbom_path=sbom_path,
        wheelhouse=wheelhouse,
        base_python=base_python,
    )
    inventory: dict[str, Any] | None = None
    if recovered_inventory_path is not None:
        value = json.loads(recovered_inventory_path.read_text(encoding="utf-8"))
        digest = value.get("artifact_sha256")
        unhashed = {key: item for key, item in value.items() if key != "artifact_sha256"}
        if digest != _canonical_sha256(unhashed):
            raise ReproducibilityError("recovered inventory content address does not verify")
        if value.get("bundle", {}).get("sha256") != manifest["data"]["sha256"]:
            raise ReproducibilityError("recovered inventory has a different data bundle")
        if value.get("application", {}).get("sha256") != manifest["source"]["sha256"]:
            raise ReproducibilityError("recovered inventory has a different application")
        inventory = {
            "artifact_sha256": digest,
            "bundle_and_application_match": True,
        }
    docker = _docker_state()
    return {
        "schema_version": RECEIPT_SCHEMA,
        "record_role": "fail_closed_private_offline_runtime_rebuild_verification",
        "runtime_manifest": manifest,
        "recovered_inventory": inventory,
        "offline_rebuild": rebuild,
        "verification_implementation": {
            "script": "scripts/reproducibility.py",
            "script_sha256": _file_sha256(Path(__file__).resolve()),
            "recipe": "reproducibility/README.md",
            "recipe_sha256": _file_sha256(root / "reproducibility/README.md"),
            "dockerfile_sha256": _file_sha256(root / "Dockerfile"),
            "dockerfile_base_image_content_pinned": False,
        },
        "host_observation": {
            "python": _run([str(base_python), "--version"], cwd=root),
            "machine": platform.machine(),
            "system": platform.system(),
            "docker": docker,
        },
        "release_gates": {
            "exact_source_and_data_manifest": True,
            "hash_locked_platform_runtime": True,
            "machine_readable_sbom": True,
            "private_offline_runtime_rebuild": True,
            "independent_reproduction": False,
            "immutable_oci_identity": False,
            "training_lineage_recovered": False,
            "payload_rights_attested": False,
            "public_redistributable_payload": False,
        },
        "status": "runtime_reconstructable_privately_release_blocked",
        "rank_eligible": False,
        "redistributable": False,
        "provider_calls_made": False,
        "epicure_network_calls_made": False,
        "limitations": [
            (
                "The embedding training run, seed, code revision, and source-corpus lineage "
                "are not recovered."
            ),
            "Payload redistribution rights and a source-rights matrix are not attested.",
            "No redistributable payload or public wheelhouse is included.",
            (
                "The same operator and checkout performed this rebuild, so it is not "
                "independent reproduction."
            ),
            "The Docker client is present but no daemon-backed immutable OCI digest was produced.",
        ],
        "official_use_rule": (
            "This receipt supports exact retrospective attribution and private runtime "
            "reconstruction. "
            "It does not authorize official ranking, public payload redistribution, an independent "
            "reproduction claim, or a recovered model-training lineage claim."
        ),
    }


def _probe(root: Path) -> dict[str, Any]:
    from epicure_mcp.provenance import build_provenance_payload

    payload = build_provenance_payload(
        str((root / "data").resolve()),
        "exploratory-unmatched-1790-runtime",
        None,
        str((root / "src/epicure_mcp").resolve()),
    )
    return {
        "release_id": payload["release_id"],
        "bundle_sha256": payload["bundle_sha256"],
        "application_sha256": payload["application_sha256"],
        "ingredient_count": payload["ingredient_count"],
        "embedding_dimensions": payload["embedding_dimensions"],
    }


def run(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sbom = subparsers.add_parser("sbom")
    sbom.add_argument("--lock", type=Path, required=True)
    sbom.add_argument("--output", type=Path, required=True)

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--root", type=Path, required=True)
    manifest.add_argument("--lock", type=Path, required=True)
    manifest.add_argument("--sbom", type=Path, required=True)
    manifest.add_argument("--output-dir", type=Path, required=True)

    receipt = subparsers.add_parser("verify-private-rebuild")
    receipt.add_argument("--root", type=Path, required=True)
    receipt.add_argument("--lock", type=Path, required=True)
    receipt.add_argument("--sbom", type=Path, required=True)
    receipt.add_argument("--wheelhouse", type=Path, required=True)
    receipt.add_argument("--base-python", type=Path, required=True)
    receipt.add_argument("--recovered-inventory", type=Path)
    receipt.add_argument("--output-dir", type=Path, required=True)

    probe = subparsers.add_parser("probe")
    probe.add_argument("--root", type=Path, required=True)

    inspect_installed = subparsers.add_parser("inspect-installed")
    inspect_installed.add_argument("--lock", type=Path, required=True)

    arguments = parser.parse_args(argv)
    if arguments.command == "sbom":
        document = build_sbom(arguments.lock)
        _write_json(arguments.output, document)
        print(
            json.dumps(
                {
                    "output": str(arguments.output.resolve()),
                    "sha256": _file_sha256(arguments.output),
                }
            )
        )
    elif arguments.command == "manifest":
        payload = build_runtime_manifest(arguments.root, arguments.lock, arguments.sbom)
        path = write_content_addressed(
            arguments.output_dir, "epicure-exact-runtime-manifest", payload
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "output": str(path.resolve()),
                    "artifact_sha256": written["artifact_sha256"],
                }
            )
        )
    elif arguments.command == "verify-private-rebuild":
        payload = build_receipt(
            root=arguments.root,
            lock_path=arguments.lock,
            sbom_path=arguments.sbom,
            wheelhouse=arguments.wheelhouse,
            base_python=arguments.base_python,
            recovered_inventory_path=arguments.recovered_inventory,
        )
        path = write_content_addressed(
            arguments.output_dir,
            "epicure-private-offline-rebuild-receipt",
            payload,
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "output": str(path.resolve()),
                    "artifact_sha256": document["artifact_sha256"],
                    "status": document["status"],
                    "rank_eligible": document["rank_eligible"],
                    "redistributable": document["redistributable"],
                    "provider_calls_made": False,
                },
                sort_keys=True,
            )
        )
    elif arguments.command == "probe":
        print(json.dumps(_probe(arguments.root), sort_keys=True))
    else:
        print(json.dumps(distribution_integrity(arguments.lock), sort_keys=True))


if __name__ == "__main__":
    run()
