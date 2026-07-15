"""Build the bundled data directory for the MCP server.

Run this once at deploy time from inside the source `epicure-data`
checkout (so `application.utils` is importable). It produces:

  data/embeddings.csv                    (copied from deploy/payload)
  data/ingredient_list.csv               (copied)
  data/ingredient_tags.csv               (copied)
  data/consolidated_nodes.csv            (copied)
  data/factor_labels_ica_cooc.json       (copied)
  data/mode_explorer_cooc.json           (copied)
  data/supervised_directions.npz         (computed)
  data/factor_dirs_ica_n20.npy           (computed)
  data/mode_poles_cooc.npy               (computed)
  data/umap_coords.csv                   (computed)
  data/umap_coords_3d.csv                (computed)

Usage:
    python scripts/build_data.py \\
        --source-repo /path/to/epicure-data \\
        --out-dir /path/to/epicure-mcp/data
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _load_aligned_embeddings(payload_dir: Path) -> tuple[np.ndarray, list[str], pd.DataFrame]:
    emb = pd.read_csv(payload_dir / "embeddings.csv")
    dim_cols = [c for c in emb.columns if c.startswith("dim_")]
    mat = emb[dim_cols].to_numpy(dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = (mat / norms).astype(np.float32)

    ing = pd.read_csv(payload_dir / "ingredient_list.csv")
    nid_to_name = dict(zip(ing["node_id"].astype(int), ing["name"].astype(str), strict=False))
    names = [nid_to_name[int(nid)] for nid in emb["node_id"].astype(int)]
    return normed, names, emb


def _copy_files(pairs: list[tuple[Path, Path]]) -> None:
    for src, dst in pairs:
        if not src.exists():
            print(f"  WARN: missing source {src}", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"  copied {src.name} -> {dst}")


def _build_supervised_directions(
    source_repo: Path, normed: np.ndarray, names: list[str], out: Path
) -> None:
    sys.path.insert(0, str(source_repo))
    from application.utils import extract_all_directions  # noqa: WPS433

    gt = pd.read_csv(source_repo / "evaluation" / "data" / "multi_language_ground_truth.csv")
    ct = pd.read_csv(source_repo / "evaluation" / "data" / "multi_language_cuisine_tags.csv")
    directions = extract_all_directions(normed, names, gt, ct)
    np.savez(out, **{k: v.astype(np.float32) for k, v in directions.items()})
    print(f"  supervised_directions.npz: {len(directions)} axes -> {out}")


def _build_factor_dirs(
    source_repo: Path,
    normed: np.ndarray,
    names: list[str],
    out: Path,
    n_factors: int = 20,
) -> None:
    sys.path.insert(0, str(source_repo))
    from application.utils import residualized_ica  # noqa: WPS433

    gt = pd.read_csv(source_repo / "evaluation" / "data" / "multi_language_ground_truth.csv")
    directions, _, _ = residualized_ica(
        normed,
        names,
        gt,
        n_factors=n_factors,
        n_seeds=10,
        seed=42,
        residualize=True,
    )
    np.save(out, directions.astype(np.float32))
    print(f"  factor_dirs_ica_n20.npy: shape={directions.shape} -> {out}")


def _build_mode_poles(
    mode_explorer_json: Path,
    normed: np.ndarray,
    names: list[str],
    out: Path,
) -> int:
    raw = json.loads(mode_explorer_json.read_text())
    name_to_row = {n: i for i, n in enumerate(names)}
    poles: list[np.ndarray] = []
    n_failed = 0
    for entry in raw:
        for mode in entry.get("modes", []):
            members = mode.get("all_members") or mode.get("top_members") or []
            member_names = [m["name"] for m in members if isinstance(m, dict) and "name" in m]
            rows = [name_to_row[n] for n in member_names if n in name_to_row]
            if len(rows) >= 2:
                vec = normed[rows].mean(axis=0)
                n = float(np.linalg.norm(vec))
                if n > 0:
                    poles.append((vec / n).astype(np.float32))
                    continue
            poles.append(np.zeros(normed.shape[1], dtype=np.float32))
            n_failed += 1
    arr = np.vstack(poles) if poles else np.zeros((0, normed.shape[1]), dtype=np.float32)
    np.save(out, arr)
    print(f"  mode_poles_cooc.npy: shape={arr.shape}, empty_modes={n_failed} -> {out}")
    return arr.shape[0]


def _build_umap(
    normed: np.ndarray,
    names: list[str],
    out: Path,
    *,
    n_components: int,
) -> None:
    import umap

    reducer = umap.UMAP(
        n_neighbors=30,
        min_dist=0.03,
        metric="cosine",
        random_state=42,
        n_components=n_components,
    )
    coords = reducer.fit_transform(normed)
    columns = {"name": names, "x": coords[:, 0], "y": coords[:, 1]}
    if n_components == 3:
        columns["z"] = coords[:, 2]
    df = pd.DataFrame(columns)
    df.to_csv(out, index=False)
    print(f"  {out.name}: shape={coords.shape} -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build epicure-mcp data bundle")
    parser.add_argument(
        "--source-repo",
        type=Path,
        default=Path("/home/jakub/epicure-data"),
        help="Path to the epicure-data checkout",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="Output directory (default: <repo>/data)",
    )
    parser.add_argument(
        "--skip-umap",
        action="store_true",
        help="Skip the UMAP step (~20 s) for quick iteration",
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    source: Path = args.source_repo
    payload = source / "deploy" / "payload"

    print(f"Building epicure-mcp data bundle into {out_dir}")
    print(f"  source repo: {source}")

    print("\n[1/5] Copying payload + paper artefacts")
    _copy_files(
        [
            (payload / "embeddings.csv", out_dir / "embeddings.csv"),
            (payload / "ingredient_list.csv", out_dir / "ingredient_list.csv"),
            (payload / "ingredient_tags.csv", out_dir / "ingredient_tags.csv"),
            (payload / "consolidated_nodes.csv", out_dir / "consolidated_nodes.csv"),
            (
                source / "application" / "paper" / "results" / "factor_labels_ica_cooc.json",
                out_dir / "factor_labels_ica_cooc.json",
            ),
            (
                source / "application" / "exploratory" / "results" / "mode_explorer_cooc.json",
                out_dir / "mode_explorer_cooc.json",
            ),
        ]
    )

    print("\n[2/5] Loading aligned embeddings")
    normed, names, _ = _load_aligned_embeddings(payload)
    print(f"  shape={normed.shape}, names={len(names)}")

    print("\n[3/5] Building supervised_directions.npz")
    _build_supervised_directions(source, normed, names, out_dir / "supervised_directions.npz")

    print("\n[4/5] Building factor_dirs_ica_n20.npy")
    _build_factor_dirs(source, normed, names, out_dir / "factor_dirs_ica_n20.npy")

    print("\n[5a/5] Building mode_poles_cooc.npy")
    _build_mode_poles(
        out_dir / "mode_explorer_cooc.json", normed, names, out_dir / "mode_poles_cooc.npy"
    )

    if args.skip_umap:
        print("\n[5b/5] Skipping UMAP (use --skip-umap=false to compute)")
    else:
        print("\n[5b/5] Building 2-D and 3-D UMAP projections")
        _build_umap(
            normed,
            names,
            out_dir / "umap_coords.csv",
            n_components=2,
        )
        _build_umap(
            normed,
            names,
            out_dir / "umap_coords_3d.csv",
            n_components=3,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
