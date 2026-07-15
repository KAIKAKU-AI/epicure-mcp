"""Pydantic models for the `morph` tool's discriminated `target` union.

Exposing this as a Pydantic-discriminated union lets FastMCP/Pydantic v2
emit a JSON Schema ``oneOf`` with ``kind`` as the discriminator. Claude
(and other MCP clients) can then validate their own ``target`` payload
against the schema before issuing the call, rather than inferring the
shape from prose.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .tool_types import AxisName, IngredientName, ModeId, PropertyName


class DirectionTarget(BaseModel):
    """Rotate the seed toward a supervised direction.

    The ``name`` is one of the keys returned by ``list_targets(kind='direction')``.
    Examples: ``cuisine:Japanese``, ``cf_sweet``, ``cf_savory``,
    ``usda_protein_g``, ``nova``, ``diet``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["direction"]
    name: AxisName = Field(
        description=(
            "Supervised direction key. Call list_targets(kind='direction') for the catalogue."
        ),
    )


class ModeTarget(BaseModel):
    """Rotate the seed toward an emergent GMM mode pole.

    ``property`` + ``mode_id`` are the two keys returned together by
    ``list_targets(kind='mode')``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["mode"]
    property: PropertyName = Field(
        description=(
            "Mode property family, e.g. 'cf_savory', 'nova_level'. Call "
            "list_targets(kind='mode') for valid (property, mode_id) pairs."
        ),
    )
    mode_id: ModeId = Field(
        description="Integer mode id within the property family.",
    )


class IngredientTarget(BaseModel):
    """Rotate the seed toward another ingredient.

    ``name`` is resolved through the same deterministic matcher as every
    other tool, so free-text inputs like ``"fresh ginger"`` work.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["ingredient"]
    name: IngredientName = Field(
        description="Target ingredient name (free-text; matcher will resolve).",
    )


MorphTarget = Annotated[
    DirectionTarget | ModeTarget | IngredientTarget,
    Field(
        discriminator="kind",
        description=(
            "Discriminated union -- exactly one of: "
            "{'kind':'direction', 'name': <axis-key>}, "
            "{'kind':'mode', 'property': <prop>, 'mode_id': <int>}, "
            "{'kind':'ingredient', 'name': <ingredient>}."
        ),
    ),
]
