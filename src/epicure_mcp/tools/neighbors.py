"""neighbors: top-k cosine neighbours of an ingredient."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..data_loader import get_bundle

DESCRIPTION = (
    "Returns the nearest ingredients to one seed by cosine similarity in the "
    "300-dimensional embedding. The result is a ranked similarity list with "
    "no clustering or dietary filtering, suited to direct substitution and "
    "single-ingredient similarity questions."
)


def run(ingredient: str, top_k: int = 5) -> dict[str, Any]:
    bundle = get_bundle()
    m = bundle.matcher.resolve(ingredient)
    if m is None:
        return {"error": f"Could not resolve ingredient '{ingredient}'"}
    row = bundle.ingredients.nid_to_row[m.node_id]
    sims = bundle.ingredients.normed @ bundle.ingredients.normed[row]
    sims[row] = -np.inf
    k = max(1, int(top_k))
    order = np.argsort(-sims)[:k]
    neighbors = [
        {
            "name": str(bundle.ingredients.names[int(i)]),
            "sim": round(float(sims[int(i)]), 4),
            "rank": rank + 1,
        }
        for rank, i in enumerate(order)
    ]
    return {"ingredient": m.name, "neighbors": neighbors}
