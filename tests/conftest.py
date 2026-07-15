"""Shared pytest fixtures.

The default fixture points the data loader at the real bundled artefacts
in ``<repo>/data``. Tests that need a tiny synthetic bundle use the
``mini_data_dir`` fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_DATA_DIR = REPO_ROOT / "data"


@pytest.fixture(scope="session")
def real_data_dir() -> Path:
    if not REAL_DATA_DIR.exists() or not (REAL_DATA_DIR / "embeddings.csv").exists():
        pytest.skip("Real data bundle not built; run scripts/build_data.py")
    return REAL_DATA_DIR


@pytest.fixture
def use_real_bundle(real_data_dir: Path, monkeypatch):
    from epicure_mcp import data_loader

    monkeypatch.setenv("EPICURE_DATA_DIR", str(real_data_dir))
    data_loader.reset_bundle_for_testing()
    yield real_data_dir
    data_loader.reset_bundle_for_testing()


@pytest.fixture
def mini_data_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "mini"
    d.mkdir()

    names = ["miso", "soy_sauce", "rice", "ginger", "olive_oil"]
    dim = 8
    rng = np.random.default_rng(0)
    base = rng.normal(size=(len(names), dim)).astype(np.float32)
    norms = np.linalg.norm(base, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    base = base / norms

    emb = pd.DataFrame(base, columns=[f"dim_{i}" for i in range(dim)])
    emb.insert(0, "node_id", range(1, len(names) + 1))
    emb.to_csv(d / "embeddings.csv", index=False)

    ing = pd.DataFrame(
        {
            "node_id": range(1, len(names) + 1),
            "name": names,
            "categories": ["Pantry"] * len(names),
            "primary_category": ["Pantry"] * len(names),
            "is_vegetarian": [True] * len(names),
            "is_vegan": [True] * len(names),
            "original_count": [1] * len(names),
        }
    )
    ing.to_csv(d / "ingredient_list.csv", index=False)

    tags = pd.DataFrame(
        {
            "node_id": range(1, len(names) + 1),
            "name": names,
            "food_group": ["Pantry"] * len(names),
            "primary_category": ["Pantry"] * len(names),
            "is_vegetarian": [True] * len(names),
            "is_vegan": [True] * len(names),
            "cuisine_region": ["universal"] * len(names),
            "nova_level": [1] * len(names),
        }
    )
    tags.to_csv(d / "ingredient_tags.csv", index=False)

    cn = pd.DataFrame(
        {
            "new_node_id": range(1, len(names) + 1),
            "final_name": names,
            "node_ids_consolidated": [f"[{i}]" for i in range(1, len(names) + 1)],
            "original_names_consolidated": [f"['{n}', 'fresh {n}']" for n in names],
        }
    )
    cn.to_csv(d / "consolidated_nodes.csv", index=False)

    direction = rng.normal(size=dim).astype(np.float32)
    direction = direction / np.linalg.norm(direction)
    np.savez(
        d / "supervised_directions.npz",
        cf_savory=direction,
        Japanese=direction,
        diet=direction,
    )

    factor_dirs = rng.normal(size=(2, dim)).astype(np.float32)
    norms = np.linalg.norm(factor_dirs, axis=1, keepdims=True)
    factor_dirs = factor_dirs / norms
    np.save(d / "factor_dirs_ica_n20.npy", factor_dirs)

    (d / "factor_labels_ica_cooc.json").write_text(
        json.dumps(
            {
                "2": {
                    "0": {
                        "axis": {"label": "Test axis", "type": "test"},
                        "pole_a": {"label": "Pole A", "coherence": "high", "themes": []},
                        "pole_b": {"label": "Pole B", "coherence": "low", "themes": []},
                        "pole_a_top": names[:2],
                        "pole_b_top": names[2:4],
                    },
                    "1": {
                        "axis": {"label": "Test axis 2", "type": "test"},
                        "pole_a": {"label": "Pole A2", "coherence": "moderate", "themes": []},
                        "pole_b": {"label": "Pole B2", "coherence": "incoherent", "themes": []},
                        "pole_a_top": names[1:3],
                        "pole_b_top": names[3:],
                    },
                }
            }
        )
    )

    (d / "mode_explorer_cooc.json").write_text(
        json.dumps(
            [
                {
                    "property": "cf_savory",
                    "modes": [
                        {
                            "mode_id": 0,
                            "size": 2,
                            "all_members": [{"name": names[0]}, {"name": names[1]}],
                            "llm_label": {"label": "Savoury mini", "confidence": "high"},
                            "dominant_cuisine": {"region": "universal"},
                            "dominant_food_group": {"label": "Pantry"},
                        }
                    ],
                }
            ]
        )
    )

    umap_df = pd.DataFrame(
        {
            "name": names,
            "x": np.arange(len(names), dtype=float),
            "y": np.arange(len(names), dtype=float),
        }
    )
    umap_df.to_csv(d / "umap_coords.csv", index=False)

    from epicure_mcp import data_loader

    monkeypatch.setenv("EPICURE_DATA_DIR", str(d))
    data_loader.reset_bundle_for_testing()
    yield d
    data_loader.reset_bundle_for_testing()
