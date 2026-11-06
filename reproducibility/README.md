# Epicure private runtime reconstruction

This directory seals the Python dependency environment used by the locally
attested `exploratory-unmatched-1790-runtime`. It is deliberately narrower than
a model release. It does not recover the embedding training run and it does not
grant permission to redistribute the data payload.

## Sealed inputs

- `runtime-linux-x86_64-cp312.lock` pins the 41 runtime dependencies observed
  in the local Python 3.12 environment. Every selected Linux x86_64 wheel has a
  SHA-256 hash and source distributions are disabled.
- `runtime-linux-x86_64-cp312.cdx.json` is a deterministic CycloneDX 1.5 SBOM.
  Its components and selected-wheel hashes are derived exactly from the lock.
- `scripts/reproducibility.py` verifies the lock, SBOM, installed distribution
  records, source manifest, data manifest, and private offline reinstall.

The lock describes the dependency environment, not the project source. Epicure
is executed from the separately content-addressed `src/epicure_mcp` tree. This
avoids treating stale editable-install metadata as source identity.

## Private rebuild

First, on a connected Linux x86_64 host with CPython 3.12, acquire the exact
wheels into a private directory:

```bash
.venv/bin/python -m pip download \
  --only-binary=:all: \
  --require-hashes \
  --dest /private/epicure-wheelhouse \
  -r reproducibility/runtime-linux-x86_64-cp312.lock
```

The remaining installation and probes use `pip --no-index`. Generate the
content-addressed verification receipt with:

```bash
.venv/bin/python scripts/reproducibility.py verify-private-rebuild \
  --root . \
  --lock reproducibility/runtime-linux-x86_64-cp312.lock \
  --sbom reproducibility/runtime-linux-x86_64-cp312.cdx.json \
  --wheelhouse /private/epicure-wheelhouse \
  --base-python .venv/bin/python \
  --recovered-inventory /private/epicure-recovered-runtime-inventory.json \
  --output-dir /private/reproducibility-receipts
```

The verifier fails closed if any wheel, installed version, RECORD-bound file,
source file, data file, or provenance identity differs. It also runs the data
shape checks in a clean temporary environment. The wheelhouse and data are not
copied into the receipt.

## Evidence boundary

The verified private rebuild establishes that the exact 1,790 by 300 payload,
the exact Python sources, and the observed dependency versions execute together
from a sealed wheelhouse. It remains an operator-local reconstruction, not an
independent reproduction.

These gates remain closed:

- original training run ID, seed, code revision, environment, and corpus
  lineage;
- payload licence, source-rights matrix, and redistribution attestation;
- a public payload or public wheelhouse;
- independent execution by another operator;
- an immutable OCI image digest. The current host has a Docker client but no
  accessible daemon, and the base-image tag is not content pinned.

Until those gates are evidenced, the runtime is suitable only for exact
retrospective attribution and private reconstruction. It is not a
redistributable release and cannot by itself authorize an official ranking.
