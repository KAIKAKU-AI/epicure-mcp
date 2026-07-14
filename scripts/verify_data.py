"""Verify the bundled data directory has every expected file with the
right rough shape. Returns non-zero exit code if anything is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_DIM = 300
EXPECTED_N_FACTORS = 20

REQUIRED_CSV = [
    "embeddings.csv",
    "ingredient_list.csv",
    "ingredient_tags.csv",
    "consolidated_nodes.csv",
]

REQUIRED_JSON = [
    "factor_labels_ica_cooc.json",
    "mode_explorer_cooc.json",
]

REQUIRED_NPY_NPZ = [
    "supervised_directions.npz",
    "factor_dirs_ica_n20.npy",
    "mode_poles_cooc.npy",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
    )
    args = parser.parse_args()
    d: Path = args.data_dir

    print(f"Verifying {d}")
    ok = True

    for fname in (
        REQUIRED_CSV
        + REQUIRED_JSON
        + REQUIRED_NPY_NPZ
        + [
            "umap_coords.csv",
            "umap_coords_3d.csv",
        ]
    ):
        path = d / fname
        if not path.exists():
            print(f"  MISSING: {fname}")
            ok = False

    if not ok:
        return 1

    emb = pd.read_csv(d / "embeddings.csv")
    dims = [c for c in emb.columns if c.startswith("dim_")]
    if len(dims) != EXPECTED_DIM:
        print(f"  WRONG DIM: embeddings has {len(dims)} dim_* cols, expected {EXPECTED_DIM}")
        ok = False
    n = len(emb)
    print(f"  embeddings: rows={n} dims={len(dims)}")

    sd = np.load(d / "supervised_directions.npz")
    print(f"  supervised_directions: keys={len(sd.files)}")
    for k in sd.files:
        if sd[k].shape != (EXPECTED_DIM,):
            print(f"    WRONG SHAPE: {k} has {sd[k].shape}")
            ok = False

    fd = np.load(d / "factor_dirs_ica_n20.npy")
    if fd.shape != (EXPECTED_N_FACTORS, EXPECTED_DIM):
        expected = (EXPECTED_N_FACTORS, EXPECTED_DIM)
        print(f"  WRONG SHAPE: factor_dirs has {fd.shape}, expected {expected}")
        ok = False
    print(f"  factor_dirs: shape={fd.shape}")

    mp = np.load(d / "mode_poles_cooc.npy")
    if mp.shape[1] != EXPECTED_DIM:
        print(f"  WRONG SHAPE: mode_poles has {mp.shape}")
        ok = False
    print(f"  mode_poles: shape={mp.shape}")

    fl = json.loads((d / "factor_labels_ica_cooc.json").read_text())
    if str(EXPECTED_N_FACTORS) not in fl:
        print(f"  MISSING factor labels for n={EXPECTED_N_FACTORS}")
        ok = False
    else:
        n_factors = len(fl[str(EXPECTED_N_FACTORS)])
        print(f"  factor_labels: {n_factors} factors at n={EXPECTED_N_FACTORS}")

    umap = pd.read_csv(d / "umap_coords.csv")
    if list(umap.columns)[:3] != ["name", "x", "y"]:
        print(f"  WRONG COLS: umap_coords has {list(umap.columns)}")
        ok = False
    print(f"  umap_coords: rows={len(umap)}")

    umap_3d = pd.read_csv(d / "umap_coords_3d.csv")
    if list(umap_3d.columns)[:4] != ["name", "x", "y", "z"]:
        print(f"  WRONG COLS: umap_coords_3d has {list(umap_3d.columns)}")
        ok = False
    if len(umap_3d) != n:
        print(f"  WRONG ROWS: umap_coords_3d has {len(umap_3d)}, expected {n}")
        ok = False
    print(f"  umap_coords_3d: rows={len(umap_3d)}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
