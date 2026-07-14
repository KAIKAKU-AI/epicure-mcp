"""pairing_score: overall cosine affinity between two ingredients."""

from __future__ import annotations

from typing import Any

from ..data_loader import get_bundle
from ..geometry import percentile_label

DESCRIPTION = (
    "Measures the affinity between two specific ingredients. Returns their "
    "300-dimensional cosine similarity and a percentile label relative to "
    "ingredient pairs in the corpus. Higher values indicate a stronger "
    "learned pairing; typical scores fall between 0.0 and 0.6."
)


def run(ingredient_a: str, ingredient_b: str) -> dict[str, Any]:
    bundle = get_bundle()
    ma = bundle.matcher.resolve(ingredient_a)
    mb = bundle.matcher.resolve(ingredient_b)
    if ma is None:
        return {"error": f"Could not resolve ingredient '{ingredient_a}'"}
    if mb is None:
        return {"error": f"Could not resolve ingredient '{ingredient_b}'"}
    ra = bundle.ingredients.nid_to_row[ma.node_id]
    rb = bundle.ingredients.nid_to_row[mb.node_id]
    score = float(bundle.ingredients.normed[ra] @ bundle.ingredients.normed[rb])
    stats = bundle.pairing_stats
    return {
        "resolved_a": ma.name,
        "resolved_b": mb.name,
        "pairing_score": round(score, 4),
        "percentile_label": percentile_label(score, stats["p10"], stats["p90"]),
        "all_pairs_range": stats,
    }
