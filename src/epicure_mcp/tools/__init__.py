"""Tool registry: every tool exports an async or sync `run(**kwargs)` function
and a `SCHEMA` describing its arguments. `register_all(server)` wires them
into the MCP server instance.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..analytics import log_call
from . import (
    closest_mode,
    compare_on_axis,
    cultural_profile,
    find_pairings,
    flavour_correlations,
    ingredient_on_factor,
    list_factors,
    list_targets,
    morph,
    neighbors,
    pairing_score,
    pareto_navigate,
    where_on_atlas,
)
from .morph_types import MorphTarget


def _wrap_result(value: Any) -> Any:
    """The MCP SDK accepts dict/list/str/numbers and serialises them. We
    leave the tool return value untouched so the SDK can attach
    structured content (preferred for MCP 2025-03-26+) plus a fallback
    JSON text block automatically."""
    return value


def register_all(server: FastMCP) -> None:
    @server.tool(
        name="compare_on_axis",
        description=compare_on_axis.DESCRIPTION,
    )
    @log_call("compare_on_axis")
    def _compare_on_axis(ingredient_a: str, ingredient_b: str, axis: str) -> Any:
        return _wrap_result(compare_on_axis.run(ingredient_a, ingredient_b, axis))

    @server.tool(
        name="pairing_score",
        description=pairing_score.DESCRIPTION,
    )
    @log_call("pairing_score")
    def _pairing_score(ingredient_a: str, ingredient_b: str) -> Any:
        return _wrap_result(pairing_score.run(ingredient_a, ingredient_b))

    @server.tool(
        name="find_pairings",
        description=find_pairings.DESCRIPTION,
    )
    @log_call("find_pairings")
    def _find_pairings(
        ingredients: list[str] | str,
        is_vegan: bool = False,
        is_vegetarian: bool = False,
        allergen_free: list[str] | None = None,
    ) -> Any:
        return _wrap_result(
            find_pairings.run(
                ingredients,
                is_vegan=is_vegan,
                is_vegetarian=is_vegetarian,
                allergen_free=allergen_free,
            )
        )

    @server.tool(
        name="flavour_correlations",
        description=flavour_correlations.DESCRIPTION,
    )
    @log_call("flavour_correlations")
    def _flavour_correlations() -> Any:
        return _wrap_result(flavour_correlations.run())

    @server.tool(
        name="cultural_profile",
        description=cultural_profile.DESCRIPTION,
    )
    @log_call("cultural_profile")
    def _cultural_profile(ingredient: str) -> Any:
        return _wrap_result(cultural_profile.run(ingredient))

    @server.tool(
        name="neighbors",
        description=neighbors.DESCRIPTION,
    )
    @log_call("neighbors")
    def _neighbors(ingredient: str, top_k: int = 5) -> Any:
        return _wrap_result(neighbors.run(ingredient, top_k=top_k))

    @server.tool(
        name="morph",
        description=morph.DESCRIPTION,
    )
    @log_call("morph")
    def _morph(
        seed: str,
        target: MorphTarget,
        angle_deg: float = 30.0,
        top_k: int = 5,
    ) -> Any:
        return _wrap_result(
            morph.run(seed=seed, target=target, angle_deg=angle_deg, top_k=top_k)
        )

    @server.tool(
        name="list_targets",
        description=list_targets.DESCRIPTION,
    )
    @log_call("list_targets")
    def _list_targets(kind: str | None = None) -> Any:
        return _wrap_result(list_targets.run(kind=kind))

    @server.tool(
        name="list_factors",
        description=list_factors.DESCRIPTION,
    )
    @log_call("list_factors")
    def _list_factors(min_coherence: str = "low") -> Any:
        return _wrap_result(list_factors.run(min_coherence=min_coherence))

    @server.tool(
        name="ingredient_on_factor",
        description=ingredient_on_factor.DESCRIPTION,
    )
    @log_call("ingredient_on_factor")
    def _ingredient_on_factor(ingredient: str, factor: int) -> Any:
        return _wrap_result(ingredient_on_factor.run(ingredient, factor))

    @server.tool(
        name="pareto_navigate",
        description=pareto_navigate.DESCRIPTION,
    )
    @log_call("pareto_navigate")
    def _pareto_navigate(
        seed: str,
        pole: dict | None = None,
        top_k_poles: int = 6,
        max_frontier: int = 15,
    ) -> Any:
        return _wrap_result(
            pareto_navigate.run(
                seed=seed,
                pole=pole,
                top_k_poles=top_k_poles,
                max_frontier=max_frontier,
            )
        )

    @server.tool(
        name="closest_mode",
        description=closest_mode.DESCRIPTION,
    )
    @log_call("closest_mode")
    def _closest_mode(ingredient: str, property: str | None = None, top_k: int = 3) -> Any:
        return _wrap_result(closest_mode.run(ingredient, property=property, top_k=top_k))

    @server.tool(
        name="where_on_atlas",
        description=where_on_atlas.DESCRIPTION,
    )
    @log_call("where_on_atlas")
    def _where_on_atlas(ingredient: str, top_k_neighbors_2d: int = 5) -> Any:
        return _wrap_result(
            where_on_atlas.run(ingredient, top_k_neighbors_2d=top_k_neighbors_2d)
        )
