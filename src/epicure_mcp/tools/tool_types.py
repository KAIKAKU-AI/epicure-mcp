"""Validated public input types shared by Epicure MCP tools."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

IngredientName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
AxisName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
PropertyName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
IngredientList = Annotated[list[IngredientName], Field(min_length=1, max_length=12)]
IngredientInput = IngredientList | IngredientName

TopK = Annotated[int, Field(ge=1, le=25)]
FactorIndex = Annotated[int, Field(ge=0, le=19)]
AngleDegrees = Annotated[float, Field(ge=0, le=90)]
ModeId = Annotated[int, Field(ge=0, le=10_000)]
CatalogueLimit = Annotated[int, Field(ge=1, le=50)]
CatalogueOffset = Annotated[int, Field(ge=0, le=10_000)]
CorrelationLimit = Annotated[int, Field(ge=1, le=100)]
CorrelationThreshold = Annotated[float, Field(ge=0.0, le=1.0)]
PoleCount = Annotated[int, Field(ge=1, le=10)]
FrontierSize = Annotated[int, Field(ge=1, le=25)]

TargetKind = Literal["direction", "mode"]
CoherenceLevel = Literal["high", "moderate", "low"]


class ParetoPole(BaseModel):
    """One labelled ICA pole used for explicit Pareto navigation."""

    model_config = ConfigDict(extra="forbid")

    factor: FactorIndex
    side: Literal["a", "b"]
