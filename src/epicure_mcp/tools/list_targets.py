"""list_targets: enumerate every valid `morph` target.

Returns supervised directions (cuisine, sensory, nutrient, NOVA, diet)
side-by-side with emergent GMM modes, plus a primer on the
``angle_deg`` parameter.
"""

from __future__ import annotations

from typing import Any

from ..data_loader import get_bundle

DESCRIPTION = (
    "Lists valid targets for morph and named axes for compare_on_axis. "
    "Directions include cuisines, sensory descriptors, nutrients, NOVA, and "
    "diet; modes are emergent GMM regions. Results are paginated by kind and "
    "include a concise angle_deg guide for morph."
)

ANGLE_DEG_PRIMER = (
    "`angle_deg` controls how far the seed is rotated toward the "
    "target on the unit sphere. Cosine-to-seed = cos(angle_deg). "
    "Useful guideposts: "
    "0deg = seed unchanged (cos=1.00); "
    "15deg = subtle nudge (cos=0.97); "
    "30deg = mild morph (cos=0.87); "
    "45deg = balanced morph (cos=0.71); "
    "60deg = strong morph (cos=0.50); "
    "90deg = orthogonal - the seed's identity is dropped entirely (cos=0)."
)


_DIRECTION_FAMILY_HINTS = {
    "cf_": "Sensory descriptor (Cooks Foundry tags).",
    "usda_": "USDA nutrient axis.",
}

_CUISINE_KEYS = {
    "Japanese",
    "East_Asian",
    "Southeast_Asian",
    "South_Asian",
    "Latin_American",
    "Mediterranean",
    "Eastern_European",
    "Western_Atlantic",
}


def _describe_direction(name: str) -> str:
    if name in _CUISINE_KEYS:
        return f"Cuisine direction for {name.replace('_', ' ')}."
    if name == "nova":
        return "NOVA processing axis (1 = whole foods, 4 = ultra-processed)."
    if name == "diet":
        return "Diet axis (animal-derived -> plant-derived)."
    for prefix, hint in _DIRECTION_FAMILY_HINTS.items():
        if name.startswith(prefix):
            return hint
    return "Supervised direction extracted from the embedding space."


def run(
    kind: str = "direction",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    if kind not in ("direction", "mode"):
        return {"error": "kind must be 'direction' or 'mode'"}
    if limit < 1 or limit > 50:
        return {"error": "limit must be between 1 and 50"}
    if offset < 0:
        return {"error": "offset must be zero or greater"}

    bundle = get_bundle()

    all_directions: list[dict[str, Any]] = []
    if kind == "direction":
        for name in sorted(bundle.directions.keys()):
            stats = bundle.direction_stats.get(name, {})
            all_directions.append(
                {
                    "kind": "direction",
                    "name": name,
                    "description": _describe_direction(name),
                    "p10": stats.get("p10"),
                    "p90": stats.get("p90"),
                }
            )

    all_modes: list[dict[str, Any]] = []
    if kind == "mode" and bundle.modes is not None:
        for prop in bundle.modes.properties:
            for mode in bundle.modes.by_property.get(prop, []):
                all_modes.append(
                    {
                        "kind": "mode",
                        "property": prop,
                        "mode_id": mode.mode_id,
                        "label": mode.label,
                        "size": mode.size,
                        "dominant_cuisine": mode.dominant_cuisine,
                        "dominant_food_group": mode.dominant_food_group,
                    }
                )

    all_items = all_directions if kind == "direction" else all_modes
    selected = all_items[offset : offset + limit]
    directions_payload = selected if kind == "direction" else []
    modes_payload = selected if kind == "mode" else []
    next_offset = offset + len(selected) if offset + len(selected) < len(all_items) else None
    return {
        "angle_deg_primer": ANGLE_DEG_PRIMER,
        "directions": directions_payload,
        "modes": modes_payload,
        "summary": {
            "kind": kind,
            "total": len(all_items),
            "returned": len(selected),
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset,
            "n_directions": len(directions_payload),
            "n_modes": len(modes_payload),
        },
    }
