"""list_factors: ICA factor catalogue with Claude-labelled poles."""

from __future__ import annotations

from typing import Any

from ..data_loader import get_bundle

DESCRIPTION = (
    "Lists the 20 emergent ICA flavour factors available to "
    "ingredient_on_factor and pareto_navigate. Each summary includes the "
    "factor index, named axis, pole labels, and coherence ratings. Set "
    "include_examples=true to add themes and anchoring ingredients, and use "
    "min_coherence to filter the catalogue."
)

_COHERENCE_RANK = {"high": 3, "moderate": 2, "low": 1, "incoherent": 0}


def _pole_payload(
    pole: dict[str, Any],
    top_names: list[str],
    *,
    include_examples: bool,
) -> dict[str, Any]:
    payload = {
        "label": pole.get("label"),
        "coherence": pole.get("coherence"),
    }
    if include_examples:
        payload["themes"] = pole.get("themes", [])
        payload["top_ingredients"] = top_names
    return payload


def _meets(coherence: str | None, threshold: int) -> bool:
    if coherence is None:
        return False
    return _COHERENCE_RANK.get(str(coherence).lower(), 0) >= threshold


def _axis_payload(axis: dict[str, Any], *, include_examples: bool) -> dict[str, Any]:
    payload = {
        "label": axis.get("label"),
        "type": axis.get("type"),
        "is_bipolar_dimension": axis.get("is_bipolar_dimension"),
    }
    if include_examples:
        payload["description"] = axis.get("description")
        payload["notes"] = axis.get("notes")
    return payload


def run(
    min_coherence: str = "moderate",
    include_examples: bool = False,
) -> dict[str, Any]:
    if min_coherence not in ("high", "moderate", "low"):
        return {"error": "min_coherence must be 'high', 'moderate', or 'low'"}

    bundle = get_bundle()
    if bundle.factors is None:
        return {"error": "No factor data bundled."}

    threshold = _COHERENCE_RANK.get(min_coherence.lower(), 1)
    factors_out: list[dict[str, Any]] = []
    for idx in sorted(bundle.factors.labels.keys()):
        entry = bundle.factors.labels[idx]
        pole_a = entry.get("pole_a") or {}
        pole_b = entry.get("pole_b") or {}
        coh_a = pole_a.get("coherence")
        coh_b = pole_b.get("coherence")
        if not (_meets(coh_a, threshold) or _meets(coh_b, threshold)):
            continue
        factors_out.append(
            {
                "factor": idx,
                "axis": _axis_payload(
                    entry.get("axis") or {},
                    include_examples=include_examples,
                ),
                "pole_a": _pole_payload(
                    pole_a,
                    entry.get("pole_a_top", []),
                    include_examples=include_examples,
                ),
                "pole_b": _pole_payload(
                    pole_b,
                    entry.get("pole_b_top", []),
                    include_examples=include_examples,
                ),
            }
        )
        if include_examples:
            factors_out[-1]["secondary_lens"] = entry.get("secondary_lens")

    return {
        "model": "cooc",
        "method": "ica",
        "n": bundle.factors.directions.shape[0],
        "min_coherence": min_coherence,
        "detail": "examples" if include_examples else "summary",
        "factors": factors_out,
    }
