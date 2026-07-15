"""find_pairings: two-tiered pairing graph for one or more ingredients.

Computes the graph in-process from the bundled embeddings + ingredient
metadata. The algorithm is a direct port of the new-epicure paper-branch
``/api/graph`` endpoint, with no external HTTP call.
"""

from __future__ import annotations

from ..data_loader import get_bundle
from ..pairings import find_pairings as _find_pairings

DESCRIPTION = (
    "Explores complementary ingredients for one or more seed ingredients. "
    "It is suited to open-ended pairing questions and recipe or dish design. "
    "Returns clustered flavour directions, each seed's strongest secondary "
    "connections, and bridge ingredients shared across clusters. Category "
    "penalties promote variety, and optional vegan or vegetarian filters "
    "remove incompatible suggestions."
)


def run(
    ingredients: list[str] | str,
    *,
    is_vegan: bool = False,
    is_vegetarian: bool = False,
) -> str:
    if isinstance(ingredients, str):
        ingredients = [ingredients]
    bundle = get_bundle()
    result = _find_pairings(
        bundle,
        list(ingredients),
        is_vegan=is_vegan,
        is_vegetarian=is_vegetarian,
    )
    if "error" in result:
        return f"Error: {result['error']}"
    return result["text"]
