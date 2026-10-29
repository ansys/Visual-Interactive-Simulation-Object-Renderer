"""
GeometryHighlight
=================
One server-side actor that draws a geometry pick: a dot at a vertex, a line
along an edge, or a cell as a translucent polygon with an opaque outline.

It is a scene actor like any other, so the parts in front of it hide it.  It is
never pickable: a part pick must pass through it.
"""

from __future__ import annotations

from typing import Sequence

from vtkmodules.vtkCommonCore import vtkPoints, vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

HIGHLIGHT_RGB: tuple[int, int, int] = (255, 165, 0)
"""Orange, as 0-255 components."""

OUTLINE_ALPHA: int = 255
"""Dots and lines are opaque."""

FILL_ALPHA: int = 89
"""A face's fill opacity, 0.35 of 255."""

POINT_SIZE: float = 12.0
LINE_WIDTH: float = 4.0

# Negative offsets pull the highlight towards the camera, so it does not fight
# the part surface it lies on.
COINCIDENT_POLYGON_OFFSET: tuple[float, float] = (-2.0, -2.0)
COINCIDENT_LINE_OFFSET: tuple[float, float] = (-2.0, -2.0)
COINCIDENT_POINT_OFFSET: float = -2.0


class GeometryHighlight:
    """A non-pickable actor drawing one geometry pick: a dot, a line, or a filled outline."""

    _polydata: vtkPolyData
    _actor: vtkActor

    def __init__(self) -> None:
        """Hidden and non-pickable, drawn in orange cell colours with lighting off."""
        self._polydata = vtkPolyData()

        mapper = vtkPolyDataMapper()
        mapper.SetInputData(self._polydata)
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
        mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(*COINCIDENT_POLYGON_OFFSET)
        mapper.SetRelativeCoincidentTopologyLineOffsetParameters(*COINCIDENT_LINE_OFFSET)
        mapper.SetRelativeCoincidentTopologyPointOffsetParameter(COINCIDENT_POINT_OFFSET)

        self._actor = vtkActor()
        self._actor.SetMapper(mapper)
        self._actor.PickableOff()
        self._actor.VisibilityOff()
        prop = self._actor.GetProperty()
        prop.LightingOff()
        prop.SetPointSize(POINT_SIZE)
        prop.SetLineWidth(LINE_WIDTH)
        prop.RenderPointsAsSpheresOn()

    @property
    def actor(self) -> vtkActor:
        """The actor to add to a renderer."""
        return self._actor

    @property
    def visible(self) -> bool:
        """Whether the actor is shown."""
        return bool(self._actor.GetVisibility())

    def show_vertex(self, position: Sequence[float]) -> None:
        """Draw one dot at position and show the actor."""
        self._draw([position], verts=[[0]], lines=[], polys=[])

    def show_edge(self, point_a: Sequence[float], point_b: Sequence[float]) -> None:
        """Draw a line between the two points, with a dot at each end, and show the actor."""
        self._draw([point_a, point_b], verts=[[0], [1]], lines=[[0, 1]], polys=[])

    def show_face(self, points: Sequence[Sequence[float]]) -> None:
        """Draw the points as a translucent polygon with an opaque closed outline, and show the actor."""
        ids = list(range(len(points)))
        self._draw(points, verts=[], lines=[ids + [0]], polys=[ids])

    def hide(self) -> None:
        """Hide the actor; the drawn geometry is kept."""
        self._actor.VisibilityOff()

    def _draw(
        self,
        points: Sequence[Sequence[float]],
        verts: list[list[int]],
        lines: list[list[int]],
        polys: list[list[int]],
    ) -> None:
        """Replace the drawn geometry: point coordinates, then vertex, line and polygon cells as point-index lists.

        Cell colours follow VTK's cell order for polydata: verts, then lines,
        then polys.
        """
        vtk_points = vtkPoints()
        for point in points:
            vtk_points.InsertNextPoint(float(point[0]), float(point[1]), float(point[2]))

        colors = vtkUnsignedCharArray()
        colors.SetNumberOfComponents(4)
        colors.SetName("HighlightColors")
        cell_arrays = []
        for cells, alpha in ((verts, OUTLINE_ALPHA), (lines, OUTLINE_ALPHA), (polys, FILL_ALPHA)):
            cell_array = vtkCellArray()
            for cell in cells:
                cell_array.InsertNextCell(len(cell), cell)
                colors.InsertNextTypedTuple((*HIGHLIGHT_RGB, alpha))
            cell_arrays.append(cell_array)

        self._polydata.Initialize()
        self._polydata.SetPoints(vtk_points)
        self._polydata.SetVerts(cell_arrays[0])
        self._polydata.SetLines(cell_arrays[1])
        self._polydata.SetPolys(cell_arrays[2])
        self._polydata.GetCellData().SetScalars(colors)
        self._actor.VisibilityOn()
