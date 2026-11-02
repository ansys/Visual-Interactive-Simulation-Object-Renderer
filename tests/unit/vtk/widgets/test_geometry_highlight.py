"""
Unit tests for GeometryHighlight, driven through each pick's highlight_with.

Every case builds a real GeometryHighlight and reads the polydata its actor's
mapper draws.  Expected values are hand-written literals.
"""

from __future__ import annotations

from ansys.visor.viewer.models.runtime.picking.geometry_pick import (
    EdgePick,
    FacePick,
    NoGeometryPick,
    VertexPick,
)
from ansys.visor.viewer.vtk.widgets.geometry_highlight import GeometryHighlight


def _drawn(highlight: GeometryHighlight):
    return highlight.actor.GetMapper().GetInput()


def _points(polydata) -> list[tuple[float, float, float]]:
    return [polydata.GetPoint(i) for i in range(polydata.GetNumberOfPoints())]


def _cells(cell_array) -> list[list[int]]:
    cells = []
    offsets = cell_array.GetOffsetsArray()
    connectivity = cell_array.GetConnectivityArray()
    for c in range(cell_array.GetNumberOfCells()):
        start, end = int(offsets.GetValue(c)), int(offsets.GetValue(c + 1))
        cells.append([int(connectivity.GetValue(i)) for i in range(start, end)])
    return cells


def test_vertex_pick_draws_one_dot_at_the_position():
    highlight = GeometryHighlight(1.0)

    VertexPick(position=[1.0, 2.0, 3.0]).highlight_with(highlight)

    drawn = _drawn(highlight)
    assert _points(drawn) == [(1.0, 2.0, 3.0)]
    assert _cells(drawn.GetVerts()) == [[0]]


def test_edge_pick_draws_a_line_and_its_end_dots():
    highlight = GeometryHighlight(1.0)

    EdgePick(point_a=[0.0, 0.0, 0.0], point_b=[3.0, 4.0, 0.0], length=5.0).highlight_with(highlight)

    drawn = _drawn(highlight)
    assert _points(drawn) == [(0.0, 0.0, 0.0), (3.0, 4.0, 0.0)]
    assert _cells(drawn.GetLines()) == [[0, 1]]
    assert _cells(drawn.GetVerts()) == [[0], [1]]


def test_face_pick_draws_the_polygon_and_its_closed_outline():
    highlight = GeometryHighlight(1.0)
    pentagon = [
        [0.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [3.0, 1.0, 0.0],
        [1.0, 2.0, 0.0],
        [-1.0, 1.0, 0.0],
    ]

    FacePick(area=5.0, points=pentagon).highlight_with(highlight)

    drawn = _drawn(highlight)
    assert _points(drawn) == [
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (3.0, 1.0, 0.0),
        (1.0, 2.0, 0.0),
        (-1.0, 1.0, 0.0),
    ]
    assert _cells(drawn.GetPolys()) == [[0, 1, 2, 3, 4]]
    assert _cells(drawn.GetLines()) == [[0, 1, 2, 3, 4, 0]]


def _rgba(polydata, cell: int) -> tuple[int, int, int, int]:
    return tuple(int(v) for v in polydata.GetCellData().GetScalars().GetTuple4(cell))


def test_vertex_point_size_is_the_css_diameter_times_the_pixel_scale():
    highlight = GeometryHighlight(2.0)

    VertexPick(position=[1.0, 2.0, 3.0]).highlight_with(highlight)

    assert highlight.actor.GetProperty().GetPointSize() == 42.0
    assert _rgba(_drawn(highlight), 0) == (255, 165, 0, 255)


def test_edge_sizes_follow_the_pixel_scale_when_it_changes():
    highlight = GeometryHighlight(1.0)
    EdgePick(point_a=[0.0, 0.0, 0.0], point_b=[3.0, 4.0, 0.0], length=5.0).highlight_with(highlight)
    prop = highlight.actor.GetProperty()
    assert (prop.GetPointSize(), prop.GetLineWidth()) == (10.0, 4.0)

    highlight.set_pixel_scale(1.5)

    assert (prop.GetPointSize(), prop.GetLineWidth()) == (15.0, 6.0)


def test_edge_dots_are_translucent_and_the_line_is_opaque():
    highlight = GeometryHighlight(1.0)

    EdgePick(point_a=[0.0, 0.0, 0.0], point_b=[3.0, 4.0, 0.0], length=5.0).highlight_with(highlight)

    drawn = _drawn(highlight)
    assert [_rgba(drawn, c) for c in range(3)] == [
        (255, 165, 0, 89),
        (255, 165, 0, 89),
        (255, 165, 0, 255),
    ]


def test_face_outline_width_is_three_css_pixels_and_the_fill_is_translucent():
    highlight = GeometryHighlight(2.0)
    triangle = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

    FacePick(area=0.5, points=triangle).highlight_with(highlight)

    assert highlight.actor.GetProperty().GetLineWidth() == 6.0
    drawn = _drawn(highlight)
    assert [_rgba(drawn, c) for c in range(2)] == [(255, 165, 0, 255), (255, 165, 0, 89)]


def test_not_found_pick_hides_a_shown_highlight():
    highlight = GeometryHighlight(1.0)
    VertexPick(position=[1.0, 2.0, 3.0]).highlight_with(highlight)
    assert highlight.visible is True

    NoGeometryPick().highlight_with(highlight)

    assert highlight.visible is False


def test_highlight_actor_is_not_pickable():
    assert GeometryHighlight(1.0).actor.GetPickable() == 0
