"""Pure-numpy geometry helpers shared by tools.

Ported from `eval/tools.py` and `application/paper/02_direction_arithmetic.py`.
"""

from __future__ import annotations

import math
from typing import cast

import numpy as np


def unit(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    if norm == 0:
        return v.astype(np.float32, copy=False)
    return cast(np.ndarray, (v / norm).astype(np.float32, copy=False))


def slerp(seed: np.ndarray, direction: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate ``seed`` toward ``direction`` on the unit sphere by ``angle_deg``.

    Both vectors are normalised first. The component of ``direction`` parallel
    to ``seed`` is removed so the rotation is along the great circle from
    ``seed`` to the orthogonal projection of ``direction``.
    """
    s = unit(seed)
    d = unit(direction)
    parallel = float(np.dot(s, d))
    perp = d - parallel * s
    perp_norm = float(np.linalg.norm(perp))
    if perp_norm < 1e-9:
        return s
    perp = perp / perp_norm
    theta = math.radians(angle_deg)
    return (math.cos(theta) * s + math.sin(theta) * perp).astype(np.float32)


def percentile_label(value: float, p10: float, p90: float) -> str:
    """Human-readable bucket for a projection within an axis distribution."""
    if value <= p10:
        return "very low (<=p10)"
    if value >= p90:
        return "very high (>=p90)"
    mid = (p10 + p90) / 2
    if value < mid - (mid - p10) * 0.3:
        return "low"
    if value > mid + (p90 - mid) * 0.3:
        return "high"
    return "moderate"


CATEGORY_PENALTY_GROUPS: dict[str, frozenset[str]] = {
    "meat": frozenset({"Meat", "Fish", "Seafood"}),
    "sweet": frozenset({"Sweet"}),
    "fat": frozenset({"Fat", "Nuts"}),
}


def category_penalty(candidate_cats: set[str], selected_cats: set[str]) -> float:
    """Mirror of the prototype `_category_penalty`; kept for the rare cases
    that the MCP server needs to penalise stack-up in its own scoring loops.
    The find_pairings tool delegates penalty handling to the upstream Epicure
    API, so this function is here for future use (e.g. local ranking)."""
    penalty = 0.0
    for group_cats in CATEGORY_PENALTY_GROUPS.values():
        if selected_cats & group_cats and candidate_cats & group_cats:
            if len(candidate_cats) == 1:
                penalty += 0.30
            else:
                penalty += 0.12
    return min(penalty, 0.60)


def distribution_stats(values: np.ndarray) -> dict[str, float]:
    return {
        "min": round(float(values.min()), 4),
        "max": round(float(values.max()), 4),
        "mean": round(float(values.mean()), 4),
        "std": round(float(values.std()), 4),
        "p10": round(float(np.percentile(values, 10)), 4),
        "p25": round(float(np.percentile(values, 25)), 4),
        "median": round(float(np.median(values)), 4),
        "p75": round(float(np.percentile(values, 75)), 4),
        "p90": round(float(np.percentile(values, 90)), 4),
    }


def pareto_frontier(
    proximity: np.ndarray,
    projection: np.ndarray,
    min_proximity: float = 0.05,
) -> list[int]:
    """Greedy non-dominated frontier on (proximity, projection).

    Returns row indices on the frontier, ordered by descending projection.
    Mirrors the algorithm in
    `application/paper/15_pareto_navigation.py`.
    """
    mask = proximity >= min_proximity
    idx = np.where(mask)[0]
    if idx.size == 0:
        return []
    order = idx[np.argsort(-projection[idx])]
    frontier: list[int] = []
    best_prox = -np.inf
    for i in order:
        if proximity[i] > best_prox:
            frontier.append(int(i))
            best_prox = float(proximity[i])
    return frontier
