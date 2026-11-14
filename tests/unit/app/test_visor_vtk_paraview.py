"""Unit tests for ``VisorVTKParaview``'s wiring of the bridge, the ParaView
scene and ``ParaviewApp``, its refusal of variable updates, and the snapshot
path it clears from user metadata but keeps on restored state.

Mocking boundary: ``visor_vtk.TrameServerManager``,
``visor_vtk_paraview.ParaviewApp``, ``visor_vtk_paraview.VisorParaviewScene``,
``visor_vtk_paraview.ServerLoopBridge`` and
``visor_vtk_paraview.ServerStatePublisher``; the file readers of the viewer's
file IO where a dataset or state is read.  Nothing here starts a trame
server or imports ParaView.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.paraview.visor_vtk_paraview import VisorVTKParaview
from ansys.visor.viewer.core.errors import UnsupportedInModeError
from ansys.visor.viewer.core.metadata import Metadata
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState


@pytest.fixture
def wiring():
    """Build a VisorVTKParaview against doubles; yield (app_cls, scene_cls, mgr, publishers, session, viewer)."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mgr_cls, \
         patch("ansys.visor.viewer.app.paraview.visor_vtk_paraview.ParaviewApp") as app_cls, \
         patch("ansys.visor.viewer.app.paraview.visor_vtk_paraview.VisorParaviewScene") as scene_cls, \
         patch("ansys.visor.viewer.app.paraview.visor_vtk_paraview.ServerLoopBridge") as bridge_cls, \
         patch("ansys.visor.viewer.app.paraview.visor_vtk_paraview.ServerStatePublisher") as publisher_cls:
        mgr = MagicMock()
        mgr.running = False
        mgr_cls.return_value = mgr
        bridge_cls.side_effect = lambda *args, **kwargs: MagicMock(name="bridge")
        publishers: list[tuple[tuple, MagicMock]] = []

        def build_publisher(*args):
            publishers.append((args, MagicMock(name="publisher")))
            return publishers[-1][1]

        publisher_cls.side_effect = build_publisher
        session = MagicMock(name="session")
        viewer = VisorVTKParaview(
            url=None,
            standalone=True,
            dark_mode=False,
            trame_log_dir=None,
            pvserver=MagicMock(name="pvserver"),
            session=session,
        )
        yield app_cls, scene_cls, mgr, publishers, session, viewer


def test_scene_receives_the_injected_session(wiring):
    """The session is stored before the base constructor builds the scene."""
    _app_cls, scene_cls, _mgr, _publishers, session, _viewer = wiring

    assert scene_cls.call_args.kwargs["session"] is session


def test_scene_and_app_share_one_bridge(wiring):
    app_cls, scene_cls, _mgr, _publishers, _session, _viewer = wiring

    assert scene_cls.call_args.kwargs["bridge"] is app_cls.call_args.kwargs["bridge"]


def test_app_receives_the_scene_members(wiring):
    """The app is given the scene itself, its RCA window, and its pick and theme methods."""
    app_cls, scene_cls, _mgr, _publishers, _session, _viewer = wiring
    scene = scene_cls.return_value
    kwargs = app_cls.call_args.kwargs

    assert kwargs["scene_mutation_api"] is scene
    assert kwargs["rca_window"] is scene.rca_window
    assert kwargs["pick_part_at"] is scene.pick_part_at
    assert kwargs["pick_geometry_at"] is scene.pick_geometry_at
    assert kwargs["set_dark_mode"] is scene.set_dark_mode


def test_scene_publishes_camera_into_the_viewer_state(wiring):
    """The scene gets the one publisher, built over this viewer's runner and server state."""
    _app_cls, scene_cls, mgr, publishers, _session, _viewer = wiring

    assert [args for args, _ in publishers] == [(mgr.async_runner, mgr.server.state)]
    assert scene_cls.call_args.kwargs["view_record_publisher"] is publishers[0][1]


def test_scene_change_bumps_the_one_publisher(wiring):
    _app_cls, _scene_cls, _mgr, publishers, _session, viewer = wiring

    viewer._post_scene_change_hook()

    publishers[0][1].bump_scene_version.assert_called_once_with()


def test_update_variables_raises_unsupported(wiring):
    *_, viewer = wiring

    with pytest.raises(UnsupportedInModeError):
        viewer.update_variables(0, [])


def added_metadata(scene_cls):
    """The metadata the scene received with the one dataset added to it."""
    scene = scene_cls.return_value
    scene.add_dataset.assert_called_once()
    return scene.add_dataset.call_args.args[1]


def add_with_metadata(scene_cls, viewer, metadata):
    scene_cls.return_value.add_dataset.return_value = 1
    with patch.object(viewer._file_io, "read_dataset", return_value=MagicMock(name="dataset")):
        viewer.add_dataset("model.vtu", metadata)


def test_user_metadata_snapshot_path_is_cleared(wiring):
    """pvserver would open a snapshot path in place of the input, so user metadata loses it."""
    _app_cls, scene_cls, *_, viewer = wiring
    metadata = Metadata(name="m", unit="mm", state={"serialized_dataset_path": "elsewhere.vtm"})

    add_with_metadata(scene_cls, viewer, metadata)

    assert added_metadata(scene_cls).state.serialized_dataset_path is None
    assert added_metadata(scene_cls).file_path == "model.vtu"
    assert metadata.state.serialized_dataset_path == "elsewhere.vtm"


def test_user_metadata_parts_are_kept(wiring):
    _app_cls, scene_cls, *_, viewer = wiring
    metadata = Metadata(
        name="m", unit="mm", state={"serialized_dataset_path": "elsewhere.vtm", "parts": {"wing": {}}}
    )

    add_with_metadata(scene_cls, viewer, metadata)

    assert list(added_metadata(scene_cls).state.parts) == ["wing"]


def test_json_metadata_snapshot_path_is_cleared(wiring, tmp_path):
    _app_cls, scene_cls, *_, viewer = wiring
    metadata_file = tmp_path / "meta.json"
    metadata_file.write_text(
        '{"name": "m", "unit": "mm", "state": {"serialized_dataset_path": "elsewhere.vtm"}}'
    )

    add_with_metadata(scene_cls, viewer, str(metadata_file))

    assert added_metadata(scene_cls).state.serialized_dataset_path is None
    assert added_metadata(scene_cls).metadata_path == str(metadata_file)


def test_load_state_keeps_snapshot_path(wiring, tmp_path):
    """Restoring state builds metadata without resolving user input, so its snapshot path is kept."""
    _app_cls, scene_cls, *_, viewer = wiring
    snapshot = tmp_path / "ds.vtm"
    snapshot.write_text("")
    state = MagicMock(name="state")
    state.scene.unit = "mm"
    state.scene.dataset_states = {"ds": PersistedDatasetState(serialized_dataset_path=str(snapshot))}
    scene_cls.return_value.dataset_count = 0

    with patch.object(viewer._file_io, "read_state", return_value=state), \
         patch.object(viewer._file_io, "read_snapshot", return_value=MagicMock(name="dataset")):
        viewer.load_state(str(tmp_path))

    assert added_metadata(scene_cls).state.serialized_dataset_path == str(snapshot)
