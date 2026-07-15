"""closest_mode: which named region of the atlas does the ingredient live in?"""

from __future__ import annotations

from typing import Any

from ..data_loader import get_bundle

DESCRIPTION = (
    "Returns the emergent GMM regions that best describe one ingredient. "
    "Each result includes a human-labelled mode, cosine similarity to its "
    "centroid, dominant cuisine and food group, and representative members. "
    "An optional property restricts the search to one axis family."
)


def run(ingredient: str, property: str | None = None, top_k: int = 3) -> dict[str, Any]:
    bundle = get_bundle()
    if bundle.modes is None:
        return {"error": "No mode data bundled."}
    m = bundle.matcher.resolve(ingredient)
    if m is None:
        return {"error": f"Could not resolve ingredient '{ingredient}'"}

    row = bundle.ingredients.nid_to_row[m.node_id]
    vec = bundle.ingredients.normed[row]
    sims = bundle.modes.pole_vectors @ vec

    candidates: list[tuple[int, str, int, float]] = []
    for (prop, mid), idx in bundle.modes.pole_index.items():
        if property is not None and prop != property:
            continue
        candidates.append((idx, prop, mid, float(sims[idx])))
    if not candidates:
        return {
            "resolved": m.name,
            "modes": [],
            "note": "No modes matched the requested filter.",
        }
    candidates.sort(key=lambda x: -x[3])
    k = max(1, int(top_k))
    selected = candidates[:k]

    modes_payload: list[dict[str, Any]] = []
    for _idx, prop, mid, score in selected:
        modes_list = bundle.modes.by_property.get(prop, [])
        mode = next((mm for mm in modes_list if mm.mode_id == mid), None)
        if mode is None:
            continue
        modes_payload.append(
            {
                "property": prop,
                "mode_id": mid,
                "label": mode.label,
                "cos_to_pole": round(score, 4),
                "size": mode.size,
                "dominant_cuisine": mode.dominant_cuisine,
                "dominant_food_group": mode.dominant_food_group,
                "top_members": mode.member_names[:10],
            }
        )

    return {
        "resolved": m.name,
        "property_filter": property,
        "modes": modes_payload,
    }
