"""Lazy, thread-safe loading of bundled artefacts.

Every artefact is loaded on first access and cached for the life of the
process. Designed to amortise a single ~200 ms cold load across all tool
calls within a worker.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, load_config
from .matcher import Matcher


@dataclass
class IngredientData:
    node_ids: np.ndarray
    names: np.ndarray
    normed: np.ndarray
    nid_to_row: dict[int, int]
    name_to_row: dict[str, int]
    primary_category: dict[int, str]
    food_group: dict[int, str]
    is_vegan: dict[int, bool]
    is_vegetarian: dict[int, bool]
    cuisine_region: dict[int, str]
    nova_level: dict[int, float]
    allergen_free: dict[str, dict[int, bool]]  # allergen_name -> {node_id: bool}


@dataclass
class Mode:
    property: str
    mode_id: int
    label: str
    size: int
    member_names: list[str]
    dominant_cuisine: str | None = None
    dominant_food_group: str | None = None


@dataclass
class ModeData:
    properties: list[str]
    by_property: dict[str, list[Mode]]
    pole_vectors: np.ndarray  # (M, 300) unit vectors
    pole_index: dict[tuple[str, int], int]


@dataclass
class FactorData:
    directions: np.ndarray  # (20, 300) unit vectors
    labels: dict[int, dict]  # factor_idx -> serialised factor metadata


@dataclass
class AtlasData:
    coords: np.ndarray  # (N, 2)
    name_to_row: dict[str, int]


@dataclass
class Bundle:
    config: Config
    matcher: Matcher
    ingredients: IngredientData
    directions: dict[str, np.ndarray] = field(default_factory=dict)
    direction_stats: dict[str, dict[str, float]] = field(default_factory=dict)
    pairing_stats: dict[str, float] = field(default_factory=dict)
    factors: FactorData | None = None
    modes: ModeData | None = None
    atlas: AtlasData | None = None


_lock = threading.Lock()
_bundle: Bundle | None = None


def _load_ingredients(cfg: Config) -> IngredientData:
    emb = pd.read_csv(cfg.embeddings_csv)
    dim_cols = [c for c in emb.columns if c.startswith("dim_")]
    mat = emb[dim_cols].to_numpy(dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = (mat / norms).astype(np.float32)
    node_ids = emb["node_id"].to_numpy(dtype=np.int64)
    nid_to_row = {int(nid): i for i, nid in enumerate(node_ids)}

    tags = pd.read_csv(cfg.ingredient_tags_csv)
    primary = {int(r.node_id): str(r.primary_category) for r in tags.itertuples()}
    food_group = {int(r.node_id): str(r.food_group) for r in tags.itertuples()}
    is_vegan = {int(r.node_id): bool(r.is_vegan) for r in tags.itertuples()}
    is_vegetarian = {int(r.node_id): bool(r.is_vegetarian) for r in tags.itertuples()}
    cuisine = {int(r.node_id): str(getattr(r, "cuisine_region", "")) for r in tags.itertuples()}
    nova: dict[int, float] = {}
    for r in tags.itertuples():
        try:
            nova[int(r.node_id)] = float(r.nova_level)
        except (TypeError, ValueError):
            pass

    # Load 14 EU allergen columns.
    ALLERGEN_COLUMNS = [
        "is_gluten_free", "is_crustacean_free", "is_egg_free", "is_fish_free",
        "is_peanut_free", "is_soy_free", "is_lactose_free", "is_nut_free",
        "is_celery_free", "is_mustard_free", "is_sesame_free", "is_sulfite_free",
        "is_lupin_free", "is_mollusc_free",
    ]
    allergen_free: dict[str, dict[int, bool]] = {}
    for col in ALLERGEN_COLUMNS:
        if col in tags.columns:
            name = col.removeprefix("is_").removesuffix("_free")  # e.g. "gluten"
            allergen_free[name] = {
                int(r.node_id): bool(getattr(r, col)) for r in tags.itertuples()
            }

    name_to_row = {}
    nid_to_name_local = {int(r.node_id): str(r.name) for r in tags.itertuples()}
    for nid, row in nid_to_row.items():
        name_to_row[nid_to_name_local[nid]] = row

    return IngredientData(
        node_ids=node_ids,
        names=np.array([nid_to_name_local[int(n)] for n in node_ids], dtype=object),
        normed=normed,
        nid_to_row=nid_to_row,
        name_to_row=name_to_row,
        primary_category=primary,
        food_group=food_group,
        is_vegan=is_vegan,
        is_vegetarian=is_vegetarian,
        cuisine_region=cuisine,
        nova_level=nova,
        allergen_free=allergen_free,
    )


def _load_directions(cfg: Config, normed: np.ndarray) -> tuple[dict, dict]:
    if not cfg.supervised_directions_npz.exists():
        return {}, {}
    data = np.load(cfg.supervised_directions_npz, allow_pickle=False)
    directions: dict[str, np.ndarray] = {}
    stats: dict[str, dict[str, float]] = {}
    for name in data.files:
        vec = data[name].astype(np.float32)
        n = float(np.linalg.norm(vec))
        if n > 0:
            vec = vec / n
        directions[name] = vec
        projections = normed @ vec
        stats[name] = {
            "min": round(float(projections.min()), 4),
            "max": round(float(projections.max()), 4),
            "mean": round(float(projections.mean()), 4),
            "std": round(float(projections.std()), 4),
            "p10": round(float(np.percentile(projections, 10)), 4),
            "p90": round(float(np.percentile(projections, 90)), 4),
        }
    return directions, stats


def _load_pairing_stats(normed: np.ndarray) -> dict[str, float]:
    n = normed.shape[0]
    rows: list[np.ndarray] = []
    for i in range(n):
        rows.append(normed[i] @ normed[i + 1:].T)
    all_sims = np.concatenate(rows)
    return {
        "p10": round(float(np.percentile(all_sims, 10)), 4),
        "p25": round(float(np.percentile(all_sims, 25)), 4),
        "median": round(float(np.median(all_sims)), 4),
        "p75": round(float(np.percentile(all_sims, 75)), 4),
        "p90": round(float(np.percentile(all_sims, 90)), 4),
    }


def _load_factors(cfg: Config) -> FactorData | None:
    if not cfg.factor_dirs_npy.exists() or not cfg.factor_labels_json.exists():
        return None
    dirs = np.load(cfg.factor_dirs_npy).astype(np.float32)
    norms = np.linalg.norm(dirs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    dirs = dirs / norms
    raw = json.loads(cfg.factor_labels_json.read_text())
    n_block = raw.get(str(dirs.shape[0])) or next(iter(raw.values()))
    labels = {int(k): v for k, v in n_block.items()}
    return FactorData(directions=dirs, labels=labels)


def _load_modes(cfg: Config, ing: IngredientData) -> ModeData | None:
    if not cfg.mode_explorer_json.exists():
        return None
    raw = json.loads(cfg.mode_explorer_json.read_text())
    properties: list[str] = []
    by_property: dict[str, list[Mode]] = {}
    pole_rows: list[np.ndarray] = []
    pole_index: dict[tuple[str, int], int] = {}

    if cfg.mode_poles_npy.exists():
        precomputed = np.load(cfg.mode_poles_npy).astype(np.float32)
    else:
        precomputed = None

    pole_counter = 0
    for entry in raw:
        prop = entry.get("property")
        if not prop:
            continue
        properties.append(prop)
        modes_list: list[Mode] = []
        for mode in entry.get("modes", []):
            mid = int(mode.get("mode_id", 0))
            members = mode.get("all_members") or mode.get("top_members") or []
            member_names = [m["name"] for m in members if isinstance(m, dict) and "name" in m]
            llm = mode.get("llm_label") or {}
            label = (
                llm.get("label")
                or mode.get("heuristic_name")
                or f"{prop} mode {mid}"
            )
            dom_cui = (mode.get("dominant_cuisine") or {}).get("region")
            dom_fg = (mode.get("dominant_food_group") or {}).get("label")
            modes_list.append(
                Mode(
                    property=prop,
                    mode_id=mid,
                    label=label,
                    size=int(mode.get("size", len(member_names))),
                    member_names=member_names,
                    dominant_cuisine=dom_cui,
                    dominant_food_group=dom_fg,
                )
            )
            if precomputed is None:
                rows = [
                    ing.name_to_row[n]
                    for n in member_names
                    if n in ing.name_to_row
                ]
                if len(rows) >= 2:
                    pole = ing.normed[rows].mean(axis=0)
                    pn = float(np.linalg.norm(pole))
                    if pn > 0:
                        pole = pole / pn
                    pole_rows.append(pole.astype(np.float32))
                else:
                    pole_rows.append(np.zeros(ing.normed.shape[1], dtype=np.float32))
            pole_index[(prop, mid)] = pole_counter
            pole_counter += 1
        by_property[prop] = modes_list

    if precomputed is not None:
        pole_vectors = precomputed
    else:
        pole_vectors = (
            np.vstack(pole_rows)
            if pole_rows
            else np.zeros((0, ing.normed.shape[1]), dtype=np.float32)
        )

    return ModeData(
        properties=properties,
        by_property=by_property,
        pole_vectors=pole_vectors,
        pole_index=pole_index,
    )


def _load_atlas(cfg: Config, ing: IngredientData) -> AtlasData | None:
    if not cfg.umap_coords_csv.exists():
        return None
    df = pd.read_csv(cfg.umap_coords_csv)
    coords = df[["x", "y"]].to_numpy(dtype=np.float32)
    name_to_row = {str(n): i for i, n in enumerate(df["name"].tolist())}
    return AtlasData(coords=coords, name_to_row=name_to_row)


def get_bundle() -> Bundle:
    """Return the singleton bundle, loading artefacts on first call."""
    global _bundle
    if _bundle is not None:
        return _bundle
    with _lock:
        if _bundle is not None:
            return _bundle
        cfg = load_config()
        matcher = Matcher(
            cfg.ingredient_list_csv,
            cfg.consolidated_nodes_csv,
            ingredient_translations_csv=cfg.ingredient_translations_csv,
        )
        ingredients = _load_ingredients(cfg)
        directions, dir_stats = _load_directions(cfg, ingredients.normed)
        pairing_stats = _load_pairing_stats(ingredients.normed)
        factors = _load_factors(cfg)
        modes = _load_modes(cfg, ingredients)
        atlas = _load_atlas(cfg, ingredients)
        _bundle = Bundle(
            config=cfg,
            matcher=matcher,
            ingredients=ingredients,
            directions=directions,
            direction_stats=dir_stats,
            pairing_stats=pairing_stats,
            factors=factors,
            modes=modes,
            atlas=atlas,
        )
    return _bundle


def reset_bundle_for_testing() -> None:
    """Clear the cached bundle. Call between tests when swapping fixtures."""
    global _bundle
    with _lock:
        _bundle = None


def reload_bundle(data_dir: Path | str | None = None) -> Bundle:
    """Force-reload with an optional override of EPICURE_DATA_DIR (testing)."""
    import os

    reset_bundle_for_testing()
    if data_dir is not None:
        os.environ["EPICURE_DATA_DIR"] = str(data_dir)
    return get_bundle()
