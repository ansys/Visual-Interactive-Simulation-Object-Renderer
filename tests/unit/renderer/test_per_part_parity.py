"""
Per-part apply parity between the local and the server renderer.

Each test runs against both renderers and asserts the part's VTK object
state after one apply, against hand-written literals.  How each renderer
publishes a write is asserted elsewhere: the server's frame request in
test_server_renderer.py, the local re-serialization in test_local_renderer.py.

The "leaves untouched" tests seed the property with non-default literals by
direct VTK writes, so that each test fails only for the method it names.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
from ansys.visor.viewer.renderer.server_renderer import ServerRenderer

PART_NODE_ID = 7
PART_RGB = [0.9, 0.1, 0.3]
SELECTION_TINT_RGB = (0.0, 62 / 255, 111 / 255)

SEEDED_AMBIENT_COLOR = (0.1, 0.2, 0.3)
SEEDED_AMBIENT = 0.25
SEEDED_DIFFUSE = 0.75
SEEDED_DIFFUSE_COLOR = (0.4, 0.5, 0.6)


class _RecordingFrameRequester:
    def __init__(self) -> None:
        self.count = 0

    def request_frame(self) -> None:
        self.count += 1


def _build_local() -> VisorLocalRenderer:
    """VisorLocalRenderer built as test_local_renderer.py's fixture builds it."""
    mock_server = MagicMock()
    mock_server.state = {}
    cross_section_widget = MagicMock(name="cross_section_widget")
    # register_node hands the widget's plane to the real mapper.
    cross_section_widget.plane = None
    with (
        patch.object(VisorLocalRenderer, "_initialize_vtk_renderer", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_render_window", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_render_window_interactor", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_local_view", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_orientation_widget", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_cross_section_widget", return_value=cross_section_widget),
        patch.object(VisorLocalRenderer, "_initialize_bounding_box_widget", return_value=MagicMock()),
    ):
        return VisorLocalRenderer(mock_server)


def _build_server() -> ServerRenderer:
    return ServerRenderer((0.2, 0.4, 0.6), _RecordingFrameRequester(), MagicMock(name="camera_publisher"))


@pytest.fixture(params=["local", "server"])
def renderer(request):
    """Either renderer, with one unit-sphere part registered."""
    r = _build_local() if request.param == "local" else _build_server()
    source = vtkSphereSource()
    source.SetRadius(1.0)
    source.Update()
    r.register_node(SimpleNamespace(id=PART_NODE_ID), source.GetOutput())
    return r


def _pipe(renderer):
    return renderer._pipelines[PART_NODE_ID]


def _seed_property(renderer) -> None:
    prop = _pipe(renderer).actor.GetProperty()
    prop.SetAmbientColor(*SEEDED_AMBIENT_COLOR)
    prop.SetAmbient(SEEDED_AMBIENT)
    prop.SetDiffuse(SEEDED_DIFFUSE)
    prop.SetDiffuseColor(*SEEDED_DIFFUSE_COLOR)


def _assert_lighting_is_seeded(prop) -> None:
    assert prop.GetAmbientColor() == pytest.approx(SEEDED_AMBIENT_COLOR)
    assert prop.GetAmbient() == SEEDED_AMBIENT
    assert prop.GetDiffuse() == SEEDED_DIFFUSE
    assert prop.GetDiffuseColor() == pytest.approx(SEEDED_DIFFUSE_COLOR)


def _apply_normals_variable(renderer) -> None:
    renderer.apply_color_variable(
        PART_NODE_ID, VisorVtkVariableType.POINT, "Normals", -1, 0.0, 1.0
    )


def test_selected_tints_and_keeps_diffuse(renderer):
    renderer.apply_selected(PART_NODE_ID, True, PART_RGB)
    prop = _pipe(renderer).actor.GetProperty()
    assert prop.GetAmbientColor() == pytest.approx(SELECTION_TINT_RGB)
    assert prop.GetAmbient() == 0.5
    assert prop.GetDiffuse() == 0.5
    assert prop.GetDiffuseColor() == pytest.approx(PART_RGB)


def test_deselected_restores_lighting(renderer):
    _seed_property(renderer)
    renderer.apply_selected(PART_NODE_ID, False, PART_RGB)
    prop = _pipe(renderer).actor.GetProperty()
    assert prop.GetAmbient() == 0.0
    assert prop.GetDiffuse() == 1.0
    assert prop.GetDiffuseColor() == pytest.approx(PART_RGB)


def test_diffuse_color_writes_only_diffuse(renderer):
    _seed_property(renderer)
    renderer.apply_diffuse_color(PART_NODE_ID, *PART_RGB)
    prop = _pipe(renderer).actor.GetProperty()
    assert prop.GetDiffuseColor() == pytest.approx(PART_RGB)
    assert prop.GetAmbientColor() == pytest.approx(SEEDED_AMBIENT_COLOR)
    assert prop.GetAmbient() == SEEDED_AMBIENT
    assert prop.GetDiffuse() == SEEDED_DIFFUSE


def test_color_variable_leaves_lighting_untouched(renderer):
    _seed_property(renderer)
    _apply_normals_variable(renderer)
    # Guards against a vacuous pass: the apply must have taken effect.
    assert _pipe(renderer).mapper.GetScalarVisibility() == 1
    _assert_lighting_is_seeded(_pipe(renderer).actor.GetProperty())


def test_clear_color_variable_only_hides_scalars(renderer):
    _apply_normals_variable(renderer)
    _seed_property(renderer)
    renderer.clear_color_variable(PART_NODE_ID)
    assert _pipe(renderer).mapper.GetScalarVisibility() == 0
    _assert_lighting_is_seeded(_pipe(renderer).actor.GetProperty())

