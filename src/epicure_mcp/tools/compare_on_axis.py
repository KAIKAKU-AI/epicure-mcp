"""compare_on_axis: project two ingredients onto one named axis and compare."""

from __future__ import annotations

from typing import Any

from ..data_loader import get_bundle
from ..geometry import percentile_label

DESCRIPTION = (
    "Compares two ingredients on one named embedding axis, such as sweetness "
    "or a cuisine direction. Returns both projections, the difference from "
    "ingredient A to ingredient B, percentile labels, and the axis p10/p90 "
    "range. Valid axis names are available from list_targets with "
    "kind='direction'."
)


def run(ingredient_a: str, ingredient_b: str, axis: str) -> dict[str, Any]:
    bundle = get_bundle()
    if axis not in bundle.directions:
        return {
            "error": f"Unknown axis '{axis}'. Call list_targets() to see valid axes.",
            "valid_axes_sample": sorted(bundle.directions.keys())[:12],
        }

    ma = bundle.matcher.resolve(ingredient_a)
    mb = bundle.matcher.resolve(ingredient_b)
    if ma is None:
        return {"error": f"Could not resolve ingredient '{ingredient_a}'"}
    if mb is None:
        return {"error": f"Could not resolve ingredient '{ingredient_b}'"}

    vec = bundle.directions[axis]
    ra = bundle.ingredients.nid_to_row[ma.node_id]
    rb = bundle.ingredients.nid_to_row[mb.node_id]
    pa = float(bundle.ingredients.normed[ra] @ vec)
    pb = float(bundle.ingredients.normed[rb] @ vec)
    stats = bundle.direction_stats[axis]
    return {
        "resolved_a": ma.name,
        "resolved_b": mb.name,
        "axis": axis,
        "projection_a": round(pa, 4),
        "label_a": percentile_label(pa, stats["p10"], stats["p90"]),
        "projection_b": round(pb, 4),
        "label_b": percentile_label(pb, stats["p10"], stats["p90"]),
        "delta": round(pb - pa, 4),
        "axis_range": {"p10": stats["p10"], "p90": stats["p90"]},
    }
