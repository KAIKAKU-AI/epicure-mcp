"""flavour_correlations: which named axes correlate with each other."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..data_loader import get_bundle

DESCRIPTION = (
    "Reports the strongest relationships between named axes in the global "
    "flavour space. Positive cosine values indicate aligned axes and negative "
    "values indicate opposing axes. Results can be limited and filtered by "
    "minimum absolute correlation to keep the response concise."
)


def run(
    limit: int = 30,
    min_abs_correlation: float = 0.3,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        return {"error": "limit must be between 1 and 100"}
    if min_abs_correlation < 0 or min_abs_correlation > 1:
        return {"error": "min_abs_correlation must be between 0 and 1"}

    bundle = get_bundle()
    names = sorted(bundle.directions.keys())
    if not names:
        return {"notable_correlations": [], "note": "No supervised directions bundled."}
    vecs = np.stack([bundle.directions[n] for n in names])
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = vecs / norms
    corr = normed @ normed.T

    notable: list[dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            c = float(corr[i, j])
            if abs(c) >= min_abs_correlation:
                notable.append(
                    {
                        "axis_a": names[i],
                        "axis_b": names[j],
                        "correlation": round(c, 3),
                    }
                )
    notable.sort(key=lambda x: -abs(x["correlation"]))
    total = len(notable)
    selected = notable[:limit]
    return {
        "n_axes": len(names),
        "min_abs_correlation": min_abs_correlation,
        "total_matches": total,
        "returned": len(selected),
        "truncated": total > len(selected),
        "notable_correlations": selected,
        "note": (
            "Cosine between unit-direction vectors. Use to understand "
            "trade-offs (e.g. sweet vs nova) when substituting ingredients."
        ),
    }
