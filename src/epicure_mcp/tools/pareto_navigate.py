"""pareto_navigate: Pareto frontier on (proximity, pole_projection).

Mirrors `application/paper/15_pareto_navigation.py`.

When ``pole`` is omitted, the tool picks the top-K poles ranked by
``|seed_projection| * coherence_weight`` (mirrors `_sort_records`).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..data_loader import get_bundle
from ..geometry import pareto_frontier

DESCRIPTION = (
    "Computes Pareto frontiers that balance similarity to a seed ingredient "
    "against movement toward one or more labelled flavour poles. It supports "
    "trade-off questions such as finding ingredients that remain rice-like "
    "while becoming more aligned with another culinary property. A specific "
    "factor and side can be supplied, or relevant poles can be selected "
    "automatically."
)

_COHERENCE_WEIGHT = {"high": 3.0, "moderate": 2.0, "low": 1.0, "incoherent": 0.0}


def _sort_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda r: -(abs(r["seed_projection"]) * r["coherence_weight"]))


def _enumerate_poles(bundle, seed_row: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fidx in range(bundle.factors.directions.shape[0]):
        direction = bundle.factors.directions[fidx]
        proj_seed = float(bundle.ingredients.normed[seed_row] @ direction)
        entry = bundle.factors.labels.get(fidx, {})
        for side, sign in (("a", +1.0), ("b", -1.0)):
            pole_meta = entry.get(f"pole_{side}") or {}
            coherence = str(pole_meta.get("coherence", "")).lower()
            weight = _COHERENCE_WEIGHT.get(coherence, 0.0)
            out.append(
                {
                    "factor": fidx,
                    "side": side,
                    "sign": sign,
                    "label": pole_meta.get("label"),
                    "coherence": coherence,
                    "seed_projection": sign * proj_seed,
                    "coherence_weight": weight,
                    "top_ingredients": entry.get(f"pole_{side}_top", []),
                    "axis": entry.get("axis", {}),
                }
            )
    return _sort_records(out)


def _frontier_for_pole(
    bundle,
    seed_row: int,
    sign: float,
    direction: np.ndarray,
    max_frontier: int,
    min_proximity: float,
) -> list[dict[str, Any]]:
    proximity = bundle.ingredients.normed @ bundle.ingredients.normed[seed_row]
    proximity[seed_row] = -np.inf
    projection = sign * (bundle.ingredients.normed @ direction)
    frontier_idx = pareto_frontier(proximity, projection, min_proximity=min_proximity)
    frontier_idx = frontier_idx[:max_frontier]
    return [
        {
            "name": str(bundle.ingredients.names[int(i)]),
            "proximity": round(float(proximity[int(i)]), 4),
            "pole_projection": round(float(projection[int(i)]), 4),
        }
        for i in frontier_idx
    ]


def run(
    *,
    seed: str,
    pole: dict[str, Any] | None = None,
    top_k_poles: int = 6,
    max_frontier: int = 15,
    min_proximity: float = 0.05,
) -> dict[str, Any]:
    bundle = get_bundle()
    if bundle.factors is None:
        return {"error": "No factor data bundled."}

    sm = bundle.matcher.resolve(seed)
    if sm is None:
        return {"error": f"Could not resolve seed ingredient '{seed}'"}
    seed_row = bundle.ingredients.nid_to_row[sm.node_id]

    poles_to_run: list[dict[str, Any]] = []
    if pole is not None:
        try:
            fidx = int(pole["factor"])
            side = str(pole["side"]).lower()
        except (KeyError, ValueError, TypeError):
            return {"error": "pole must be {factor:int, side:'a'|'b'}"}
        if side not in ("a", "b"):
            return {"error": "pole.side must be 'a' or 'b'"}
        sign = +1.0 if side == "a" else -1.0
        entry = bundle.factors.labels.get(fidx, {})
        pole_meta = entry.get(f"pole_{side}") or {}
        poles_to_run.append(
            {
                "factor": fidx,
                "side": side,
                "sign": sign,
                "label": pole_meta.get("label"),
                "coherence": pole_meta.get("coherence"),
                "top_ingredients": entry.get(f"pole_{side}_top", []),
                "axis": entry.get("axis", {}),
                "seed_projection": sign
                * float(bundle.ingredients.normed[seed_row] @ bundle.factors.directions[fidx]),
            }
        )
    else:
        ranked = _enumerate_poles(bundle, seed_row)
        poles_to_run = [p for p in ranked if p["coherence_weight"] > 0][:top_k_poles]

    poles_payload: list[dict[str, Any]] = []
    for p in poles_to_run:
        direction = bundle.factors.directions[p["factor"]]
        frontier = _frontier_for_pole(
            bundle,
            seed_row,
            p["sign"],
            direction,
            max_frontier,
            min_proximity,
        )
        poles_payload.append(
            {
                "factor": p["factor"],
                "side": p["side"],
                "label": p["label"],
                "coherence": p.get("coherence"),
                "axis": p.get("axis", {}),
                "seed_projection": round(float(p["seed_projection"]), 4),
                "top_ingredients_at_pole": p.get("top_ingredients", []),
                "frontier": frontier,
            }
        )

    return {
        "seed": sm.name,
        "n_poles": len(poles_payload),
        "poles": poles_payload,
    }
