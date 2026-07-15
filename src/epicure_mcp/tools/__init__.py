"""Tool registry: every tool exports an async or sync `run(**kwargs)` function
and a `SCHEMA` describing its arguments. `register_all(server)` wires them
into the MCP server instance.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

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
from .tool_types import (
    AngleDegrees,
    AxisName,
    CatalogueLimit,
    CatalogueOffset,
    CoherenceLevel,
    CorrelationLimit,
    CorrelationThreshold,
    FactorIndex,
    FrontierSize,
    IngredientInput,
    IngredientName,
    ParetoPole,
    PoleCount,
    PropertyName,
    TargetKind,
    TopK,
)

# ChatGPT's Apps SDK reads this compatibility metadata to distinguish tools
# that are intentionally public from tools that inherit an OAuth requirement.
# Keep the declaration on every tool so anonymous access is unambiguous.
NOAUTH_TOOL_META: dict[str, Any] = {
    "securitySchemes": [{"type": "noauth"}],
}


def _read_only(title: str) -> ToolAnnotations:
    """Return the complete read-only annotation set required by directories."""
    return ToolAnnotations(
        title=title,
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


def _wrap_result(value: Any) -> Any:
    """Raise protocol-level tool errors while preserving structured results."""
    if isinstance(value, dict) and isinstance(value.get("error"), str):
        raise ToolError(value["error"])
    if isinstance(value, str) and value.lstrip().lower().startswith("error:"):
        raise ToolError(value.split(":", 1)[1].strip())
    return value


def register_all(server: FastMCP) -> None:
    title = "Compare ingredients on an axis"

    @server.tool(
        name="compare_on_axis",
        title=title,
        description=compare_on_axis.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("compare_on_axis")
    def _compare_on_axis(
        ingredient_a: IngredientName,
        ingredient_b: IngredientName,
        axis: AxisName,
    ) -> Any:
        return _wrap_result(compare_on_axis.run(ingredient_a, ingredient_b, axis))

    title = "Score an ingredient pairing"

    @server.tool(
        name="pairing_score",
        title=title,
        description=pairing_score.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("pairing_score")
    def _pairing_score(
        ingredient_a: IngredientName,
        ingredient_b: IngredientName,
    ) -> Any:
        return _wrap_result(pairing_score.run(ingredient_a, ingredient_b))

    title = "Explore ingredient pairings"

    @server.tool(
        name="find_pairings",
        title=title,
        description=find_pairings.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("find_pairings")
    def _find_pairings(
        ingredients: IngredientInput,
        is_vegan: bool = False,
        is_vegetarian: bool = False,
    ) -> Any:
        return _wrap_result(
            find_pairings.run(ingredients, is_vegan=is_vegan, is_vegetarian=is_vegetarian)
        )

    title = "Inspect flavour correlations"

    @server.tool(
        name="flavour_correlations",
        title=title,
        description=flavour_correlations.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("flavour_correlations")
    def _flavour_correlations(
        limit: CorrelationLimit = 30,
        min_abs_correlation: CorrelationThreshold = 0.3,
    ) -> Any:
        return _wrap_result(
            flavour_correlations.run(
                limit=limit,
                min_abs_correlation=min_abs_correlation,
            )
        )

    title = "Profile an ingredient by cuisine"

    @server.tool(
        name="cultural_profile",
        title=title,
        description=cultural_profile.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("cultural_profile")
    def _cultural_profile(ingredient: IngredientName) -> Any:
        return _wrap_result(cultural_profile.run(ingredient))

    title = "Find similar ingredients"

    @server.tool(
        name="neighbors",
        title=title,
        description=neighbors.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("neighbors")
    def _neighbors(ingredient: IngredientName, top_k: TopK = 5) -> Any:
        return _wrap_result(neighbors.run(ingredient, top_k=top_k))

    title = "Transform an ingredient in flavour space"

    @server.tool(
        name="morph",
        title=title,
        description=morph.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("morph")
    def _morph(
        seed: IngredientName,
        target: MorphTarget,
        angle_deg: AngleDegrees = 30.0,
        top_k: TopK = 5,
    ) -> Any:
        return _wrap_result(morph.run(seed=seed, target=target, angle_deg=angle_deg, top_k=top_k))

    title = "List transformation targets"

    @server.tool(
        name="list_targets",
        title=title,
        description=list_targets.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("list_targets")
    def _list_targets(
        kind: TargetKind = "direction",
        limit: CatalogueLimit = 25,
        offset: CatalogueOffset = 0,
    ) -> Any:
        return _wrap_result(list_targets.run(kind=kind, limit=limit, offset=offset))

    title = "List flavour factors"

    @server.tool(
        name="list_factors",
        title=title,
        description=list_factors.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("list_factors")
    def _list_factors(
        min_coherence: CoherenceLevel = "moderate",
        include_examples: bool = False,
    ) -> Any:
        return _wrap_result(
            list_factors.run(
                min_coherence=min_coherence,
                include_examples=include_examples,
            )
        )

    title = "Project an ingredient onto a factor"

    @server.tool(
        name="ingredient_on_factor",
        title=title,
        description=ingredient_on_factor.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("ingredient_on_factor")
    def _ingredient_on_factor(
        ingredient: IngredientName,
        factor: FactorIndex,
    ) -> Any:
        return _wrap_result(ingredient_on_factor.run(ingredient, factor))

    title = "Navigate a flavour trade-off"

    @server.tool(
        name="pareto_navigate",
        title=title,
        description=pareto_navigate.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("pareto_navigate")
    def _pareto_navigate(
        seed: IngredientName,
        pole: ParetoPole | None = None,
        top_k_poles: PoleCount = 6,
        max_frontier: FrontierSize = 15,
    ) -> Any:
        return _wrap_result(
            pareto_navigate.run(
                seed=seed,
                pole=pole.model_dump() if pole is not None else None,
                top_k_poles=top_k_poles,
                max_frontier=max_frontier,
            )
        )

    title = "Find an ingredient's flavour region"

    @server.tool(
        name="closest_mode",
        title=title,
        description=closest_mode.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("closest_mode")
    def _closest_mode(
        ingredient: IngredientName,
        property: PropertyName | None = None,
        top_k: TopK = 3,
    ) -> Any:
        return _wrap_result(closest_mode.run(ingredient, property=property, top_k=top_k))

    title = "Locate an ingredient on the atlas"

    @server.tool(
        name="where_on_atlas",
        title=title,
        description=where_on_atlas.DESCRIPTION,
        annotations=_read_only(title),
        meta=NOAUTH_TOOL_META,
    )
    @log_call("where_on_atlas")
    def _where_on_atlas(
        ingredient: IngredientName,
        top_k_neighbors_2d: TopK = 5,
    ) -> Any:
        return _wrap_result(where_on_atlas.run(ingredient, top_k_neighbors_2d=top_k_neighbors_2d))
