"""
Geometry pick results
=====================
The four results a geometry pick can report.  Each dumps by alias to the
wire shape the client's result panel reads.
"""

from __future__ import annotations

from typing import List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

GeometryPickMode = Literal["vertex", "edge", "face"]


class NoGeometryPick(BaseModel):
    """No part cell under the pick."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[False] = False


class VertexPick(BaseModel):
    """The picked cell's vertex nearest the pick position."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[True] = True
    mode: Literal["vertex"] = "vertex"
    position: List[float]


class EdgePick(BaseModel):
    """The picked cell's edge nearest the pick position, with its length."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[True] = True
    mode: Literal["edge"] = "edge"
    point_a: List[float] = Field(alias="pointA")
    point_b: List[float] = Field(alias="pointB")
    length: float


class FacePick(BaseModel):
    """The picked cell as a whole, with its area."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[True] = True
    mode: Literal["face"] = "face"
    area: float
    points: List[List[float]]


GeometryPick = Union[VertexPick, EdgePick, FacePick, NoGeometryPick]
