"""
Geometry pick results
=====================
The four results a geometry pick can report.  Each dumps by alias to the
wire shape the client's result panel reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ansys.visor.viewer.vtk.widgets.geometry_highlight import GeometryHighlight

GeometryPickMode = Literal["vertex", "edge", "face"]


class NoGeometryPick(BaseModel):
    """No part cell under the pick."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[False] = False

    def highlight_with(self, highlight: "GeometryHighlight") -> None:
        """Hide the highlight."""
        highlight.hide()


class VertexPick(BaseModel):
    """The picked cell's vertex nearest the pick position."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[True] = True
    mode: Literal["vertex"] = "vertex"
    position: List[float]

    def highlight_with(self, highlight: "GeometryHighlight") -> None:
        """Draw a dot at the vertex."""
        highlight.show_vertex(self.position)


class EdgePick(BaseModel):
    """The picked cell's edge nearest the pick position, with its length."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[True] = True
    mode: Literal["edge"] = "edge"
    point_a: List[float] = Field(alias="pointA")
    point_b: List[float] = Field(alias="pointB")
    length: float

    def highlight_with(self, highlight: "GeometryHighlight") -> None:
        """Draw a line along the edge."""
        highlight.show_edge(self.point_a, self.point_b)


class FacePick(BaseModel):
    """The picked cell as a whole, with its area."""

    model_config = ConfigDict(populate_by_name=True)

    found: Literal[True] = True
    mode: Literal["face"] = "face"
    area: float
    points: List[List[float]]

    def highlight_with(self, highlight: "GeometryHighlight") -> None:
        """Draw the cell as a filled outline."""
        highlight.show_face(self.points)


GeometryPick = Union[VertexPick, EdgePick, FacePick, NoGeometryPick]
