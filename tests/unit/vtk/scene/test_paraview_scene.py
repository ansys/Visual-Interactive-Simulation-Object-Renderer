"""
Unit tests for VisorParaviewScene.

Each test builds a real VisorParaviewScene, so a real ParaviewRenderer and a
real trame-rca capture, over a recording fake session whose render window is a
real off-screen VTK window.  No ParaView is imported and no test renders a
frame.  Expected values are hand-written literals; colours are the client
CSS's 0-255 triples.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkRenderWindowInteractor

from ansys.visor.viewer.core.errors import UnsupportedInModeError, VisorAddDatasetError
from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.models.runtime.picking.geometry_pick import NoGeometryPick
from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from ansys.visor.viewer.vtk.scene import paraview_scene
from ansys.visor.viewer.vtk.scene.paraview_scene import VisorParaviewScene
from tests.helpers.utils.locks import LockSpy, lock_held_by_another_thread

LIGHT_CSS_RGB = (247, 247, 247)
DARK_CSS_RGB = (54, 60, 67)
MANY_BLOCKS_VTM = Path(__file__).parents[3] / "files" / "many_blocks" / "many_blocks.vtm"


class _FakeSession:
    """Records the session calls a scene makes; the render window is a real off-screen window."""

    def __init__(self, point_count: int = 3) -> None:
        window = vtkRenderWindow()
        window.SetOffScreenRendering(1)
        interactor = vtkRenderWindowInteractor()
        interactor.SetRenderWindow(window)
        self.render_window = window
        self._interactor = interactor
        self.reported_points = point_count
        self.opened: list[str] = []
        self.shown: list[object] = []
        self.writes: list[tuple[str, object]] = []
        self.deleted: list[object] = []
        self.backgrounds: list[tuple[float, float, float]] = []
        self.render_count = 0

    def open(self, path):
        self.opened.append(path)
        return SimpleNamespace(path=path)

    def show(self, source):
        self.shown.append(source)
        return SimpleNamespace(shows=source)

    def delete(self, source):
        self.deleted.append(source)

    def point_count(self, source):
        return self.reported_points

    def block_point_count(self, source, selector):
        return self.reported_points

    def set_property(self, rep, name, value):
        self.writes.append((name, value))

    def clear_color(self, rep):
        pass

    def new_color_map(self, component):
        return SimpleNamespace(component=component)

    def rescale_color_map(self, lut, lo, hi):
        pass

    def delete_color_map(self, lut):
        pass

    def set_selected_blocks(self, source, selectors):
        pass

    def write_camera(self, camera):
        pass

    def read_camera(self):
        return None

    def reset_camera(self, bounds):
        pass

    def set_background(self, rgb):
        self.backgrounds.append(rgb)

    def set_viewport_size(self, width, height):
        pass

    def render(self):
        self.render_count += 1


class _RecordingBridge:
    """Counts frame requests and retries."""

    def __init__(self) -> None:
        self.request_count = 0
        self.retry_count = 0

    def request_frame(self) -> None:
        self.request_count += 1

    def retry_frame(self) -> None:
        self.retry_count += 1


def _triangle_points() -> vtkPolyData:
    """Three points, no arrays."""
    points = vtkPoints()
    points.InsertNextPoint(0.0, 0.0, 0.0)
    points.InsertNextPoint(1.0, 0.0, 0.0)
    points.InsertNextPoint(0.0, 1.0, 0.0)
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    return polydata


def _metadata(name: str, file_path: str | None = None, snapshot_path: str | None = None) -> ExtendedMetadata:
    return ExtendedMetadata(
        name=name, unit="m", file_path=file_path, state={"serialized_dataset_path": snapshot_path}
    )


def _css_rgb(rgb) -> tuple[int, int, int]:
    """A 0-1 colour as the 0-255 triple a CSS variable holds."""
    return tuple(round(c * 255) for c in rgb)


@pytest.fixture
def session() -> _FakeSession:
    return _FakeSession()


@pytest.fixture
def bridge() -> _RecordingBridge:
    return _RecordingBridge()


@pytest.fixture
def scene(session, bridge) -> VisorParaviewScene:
    """A light-theme scene with no datasets; bridge counts start at zero."""
    s = VisorParaviewScene(MagicMock(name="server"), False, bridge, MagicMock(name="publisher"), session)
    bridge.request_count = 0
    bridge.retry_count = 0
    return s


def _record_open_source_keys(scene: VisorParaviewScene) -> list[str]:
    keys: list[str] = []
    open_source = scene._renderer.open_source

    def recording_open_source(dataset_key, server_path, local_root):
        keys.append(dataset_key)
        open_source(dataset_key, server_path, local_root)

    scene._renderer.open_source = recording_open_source
    return keys


# ---------------------------------------------------------------------------
# server_path
# ---------------------------------------------------------------------------


def test_server_path_prefers_the_snapshot():
    metadata = _metadata("a", file_path="/shared/a.vtp", snapshot_path="/state/a.vtkhdf")
    assert VisorParaviewScene.server_path(metadata) == "/state/a.vtkhdf"


def test_server_path_falls_back_to_the_input_file():
    assert VisorParaviewScene.server_path(_metadata("a", file_path="/shared/a.vtp")) == "/shared/a.vtp"


def test_server_path_raises_for_in_memory_input():
    with pytest.raises(UnsupportedInModeError):
        VisorParaviewScene.server_path(_metadata("a"))


# ---------------------------------------------------------------------------
# add_dataset
# ---------------------------------------------------------------------------


def test_add_dataset_opens_the_input_file_on_pvserver(scene, session):
    scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    assert session.opened == ["/shared/a.vtp"]


def test_add_dataset_registers_the_dataset(scene):
    dataset_id = scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    assert list(scene.datasets) == [dataset_id]


def test_two_datasets_open_under_distinct_keys(scene):
    keys = _record_open_source_keys(scene)
    scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    scene.add_dataset(_triangle_points(), _metadata("b", file_path="/shared/b.vtp"))
    assert keys == ["pv-0", "pv-1"]


def test_add_dataset_holds_lock_when_opening(scene):
    scene._vtk_lock = LockSpy()
    depths = []
    open_source = scene._renderer.open_source

    def recording_open_source(dataset_key, server_path, local_root):
        depths.append(scene._vtk_lock.depth)
        open_source(dataset_key, server_path, local_root)

    scene._renderer.open_source = recording_open_source
    scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    assert depths == [1]


def test_failed_add_raises(session, bridge):
    session.reported_points = 99
    s = VisorParaviewScene(MagicMock(name="server"), False, bridge, MagicMock(name="publisher"), session)
    with pytest.raises(VisorAddDatasetError):
        s.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))


def test_failed_add_deletes_the_opened_source(session, bridge):
    session.reported_points = 99
    s = VisorParaviewScene(MagicMock(name="server"), False, bridge, MagicMock(name="publisher"), session)
    with pytest.raises(VisorAddDatasetError):
        s.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    assert [source.path for source in session.deleted] == ["/shared/a.vtp"]


def test_in_memory_input_opens_nothing(scene, session):
    with pytest.raises(UnsupportedInModeError):
        scene.add_dataset(_triangle_points(), _metadata("a"))
    assert session.opened == []


def test_add_multiblock_shows_one_representation(scene, session):
    session.reported_points = 88
    scene.add_dataset(file_to_dataset(str(MANY_BLOCKS_VTM)), _metadata("mb", file_path="/shared/many_blocks.vtm"))
    shown_blocks = [value for name, value in session.writes if name == "BlockSelectors"][-1]
    assert (len(session.shown), len(shown_blocks), shown_blocks[:3]) == (
        1,
        66,
        [
            "/Root/GroupA/GroupAA/Block0",
            "/Root/GroupA/GroupAA/GroupAAA/Block0",
            "/Root/GroupA/GroupAA/GroupAAA/Block1",
        ],
    )


# ---------------------------------------------------------------------------
# remove_dataset and clear
# ---------------------------------------------------------------------------


def test_remove_dataset_deletes_its_pvserver_source(scene, session):
    dataset_id = scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    scene.remove_dataset(dataset_id)
    assert [source.path for source in session.deleted] == ["/shared/a.vtp"]


def test_remove_dataset_deletes_only_its_own_source(scene, session):
    scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    second = scene.add_dataset(_triangle_points(), _metadata("b", file_path="/shared/b.vtp"))
    scene.remove_dataset(second)
    assert [source.path for source in session.deleted] == ["/shared/b.vtp"]


def test_remove_dataset_unregisters_the_dataset(scene):
    dataset_id = scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    scene.remove_dataset(dataset_id)
    assert list(scene.datasets) == []


def test_remove_multiblock_dataset_deletes_only_its_source(scene, session):
    session.reported_points = 88
    dataset_id = scene.add_dataset(
        file_to_dataset(str(MANY_BLOCKS_VTM)), _metadata("mb", file_path="/shared/many_blocks.vtm")
    )
    scene.remove_dataset(dataset_id)
    assert [source.path for source in session.deleted] == ["/shared/many_blocks.vtm"]


def test_remove_dataset_holds_lock_when_closing(scene):
    dataset_id = scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    scene._vtk_lock = LockSpy()
    depths = []
    close_source = scene._renderer.close_source

    def recording_close_source(dataset_key):
        depths.append(scene._vtk_lock.depth)
        close_source(dataset_key)

    scene._renderer.close_source = recording_close_source
    scene.remove_dataset(dataset_id)
    assert depths == [1]


def test_clear_deletes_every_pvserver_source(scene, session):
    scene.add_dataset(_triangle_points(), _metadata("a", file_path="/shared/a.vtp"))
    scene.add_dataset(_triangle_points(), _metadata("b", file_path="/shared/b.vtp"))
    scene.clear()
    assert sorted(source.path for source in session.deleted) == ["/shared/a.vtp", "/shared/b.vtp"]


# ---------------------------------------------------------------------------
# Background follows the theme
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dark_mode", "expected"),
    [(False, LIGHT_CSS_RGB), (True, DARK_CSS_RGB)],
    ids=["light", "dark"],
)
def test_initial_background_follows_theme(session, bridge, dark_mode, expected):
    VisorParaviewScene(MagicMock(name="server"), dark_mode, bridge, MagicMock(name="publisher"), session)
    assert _css_rgb(session.backgrounds[-1]) == expected


def test_set_dark_mode_recolors_background(scene, session):
    scene.set_dark_mode(True)
    assert _css_rgb(session.backgrounds[-1]) == DARK_CSS_RGB


def test_set_dark_mode_sets_dark_mode(scene):
    scene.set_dark_mode(True)
    assert scene.dark_mode is True


def test_set_dark_mode_requests_one_frame(scene, bridge):
    scene.set_dark_mode(True)
    assert bridge.request_count == 1


def test_set_dark_mode_holds_lock(scene):
    scene._vtk_lock = LockSpy()
    depths = []
    set_background_rgb = scene._renderer.set_background_rgb

    def recording_set_background_rgb(background_rgb):
        depths.append(scene._vtk_lock.depth)
        set_background_rgb(background_rgb)

    scene._renderer.set_background_rgb = recording_set_background_rgb
    scene.set_dark_mode(True)
    assert depths == [1]


def test_push_runtime_state_requests_one_frame(scene, bridge):
    scene._push_runtime_state(scene._current_runtime_state())
    assert bridge.request_count == 1


# ---------------------------------------------------------------------------
# Picking
# ---------------------------------------------------------------------------


def test_pick_part_at_returns_none(scene):
    assert scene.pick_part_at(31, 17) is None


def test_pick_part_at_logs_a_warning(scene, monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(paraview_scene, "logger", logger)
    scene.pick_part_at(31, 17)
    logger.warning.assert_called_once_with("part picking is not supported in PARAVIEW mode")


def test_pick_geometry_at_returns_an_empty_pick(scene):
    pick = scene.pick_geometry_at(31, 17, "vertex")
    assert (type(pick), pick.found) == (NoGeometryPick, False)


def test_pick_geometry_at_logs_a_warning(scene, monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(paraview_scene, "logger", logger)
    scene.pick_geometry_at(31, 17, "vertex")
    logger.warning.assert_called_once_with("geometry picking is not supported in PARAVIEW mode")


# ---------------------------------------------------------------------------
# RCA window
# ---------------------------------------------------------------------------


def test_rca_window_wraps_scene_lock(scene, bridge):
    with lock_held_by_another_thread(scene._vtk_lock):
        _ = scene.rca_window.img_cols_rows
    assert bridge.retry_count == 1
