"""morph: unified SLERP over direction / mode / ingredient targets.

Given a seed ingredient and a target vector, rotate the seed on the unit
sphere toward the target by ``angle_deg`` and return the top-k nearest
ingredients to the rotated query.

The ``target`` payload is a discriminated union:
- ``{"kind": "direction", "name": "<key>"}`` - a supervised axis (cuisine,
  sensory, nutrient, NOVA, diet)
- ``{"kind": "mode", "property": "<prop>", "mode_id": <int>}`` - an
  emergent GMM mode pole
- ``{"kind": "ingredient", "name": "<ing>"}`` - rotate the seed toward
  another ingredient
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..data_loader import get_bundle
from ..geometry import slerp

DESCRIPTION = (
    "Rotates a seed ingredient toward a named direction, emergent mode, or "
    "second ingredient on the embedding unit sphere, then returns the nearest "
    "ingredients to the transformed vector. This supports explicitly directed "
    "transformations such as making an ingredient sweeter or more aligned with "
    "a cuisine. list_targets provides valid directions and modes. angle_deg "
    "ranges from 0 (unchanged) to 90 (fully orthogonal to the seed)."
)


def _to_dict(target: Any) -> dict[str, Any]:
    """Accept either a Pydantic model (from FastMCP-validated input) or a
    raw dict (from in-process test calls / older clients)."""
    if hasattr(target, "model_dump"):
        return target.model_dump()
    if isinstance(target, dict):
        return target
    return {}


def _resolve_target(target: Any) -> tuple[np.ndarray | None, dict[str, Any]]:
    bundle = get_bundle()
    target = _to_dict(target)
    kind = target.get("kind")
    if kind == "direction":
        name = target.get("name")
        if not isinstance(name, str):
            return None, {"error": "target.name must be a string for kind='direction'"}
        if name not in bundle.directions:
            return None, {
                "error": f"Unknown direction '{name}'. Call list_targets() to see valid names.",
            }
        return bundle.directions[name], {"resolved_target": f"direction:{name}"}

    if kind == "mode":
        prop = target.get("property")
        mid = target.get("mode_id")
        if not isinstance(prop, str) or not isinstance(mid, int):
            return None, {
                "error": (
                    "target.property must be a string and target.mode_id an int for kind='mode'"
                ),
            }
        if bundle.modes is None:
            return None, {"error": "Mode data not bundled."}
        idx = bundle.modes.pole_index.get((prop, mid))
        if idx is None:
            return None, {"error": f"Unknown mode ({prop}, {mid})."}
        modes_list = bundle.modes.by_property.get(prop, [])
        label = next(
            (m.label for m in modes_list if m.mode_id == mid),
            f"{prop}/M{mid}",
        )
        return bundle.modes.pole_vectors[idx], {
            "resolved_target": f"mode:{prop}/M{mid}",
            "mode_label": label,
        }

    if kind == "ingredient":
        name = target.get("name")
        if not isinstance(name, str):
            return None, {"error": "target.name must be a string for kind='ingredient'"}
        m = bundle.matcher.resolve(name)
        if m is None:
            return None, {"error": f"Could not resolve ingredient target '{name}'"}
        row = bundle.ingredients.nid_to_row[m.node_id]
        return bundle.ingredients.normed[row], {
            "resolved_target": f"ingredient:{m.name}",
        }

    return None, {
        "error": (
            "target.kind must be one of 'direction', 'mode', 'ingredient'. "
            "Call list_targets() for a catalogue."
        ),
    }


def run(
    *,
    seed: str,
    target: Any,
    angle_deg: float = 30.0,
    top_k: int = 5,
) -> dict[str, Any]:
    bundle = get_bundle()
    sm = bundle.matcher.resolve(seed)
    if sm is None:
        return {"error": f"Could not resolve seed ingredient '{seed}'"}

    target_vec, target_meta = _resolve_target(target)
    if target_vec is None:
        return target_meta

    seed_row = bundle.ingredients.nid_to_row[sm.node_id]
    seed_vec = bundle.ingredients.normed[seed_row]
    rotated = slerp(seed_vec, target_vec, float(angle_deg))
    sims = bundle.ingredients.normed @ rotated
    sims[seed_row] = -np.inf
    order = np.argsort(-sims)[: max(1, int(top_k))]
    neighbors = [
        {
            "name": str(bundle.ingredients.names[int(i)]),
            "sim": round(float(sims[int(i)]), 4),
        }
        for i in order
    ]
    cos_to_seed = float(np.cos(np.deg2rad(float(angle_deg))))
    return {
        "seed": sm.name,
        "angle_deg": float(angle_deg),
        "cos_to_seed": round(cos_to_seed, 4),
        **target_meta,
        "neighbors": neighbors,
    }
