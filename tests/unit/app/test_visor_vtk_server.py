"""Unit tests for ``VisorVTKServer``'s wiring of the bridge, the server scene
and ``ServerApp``.

Mocking boundary: ``visor_vtk.TrameServerManager``,
``visor_vtk_server.ServerApp``, ``visor_vtk_server.VisorServerScene``,
``visor_vtk_server.ServerLoopBridge`` and
``visor_vtk_server.ServerStatePublisher``.  Nothing here starts a trame server.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.visor_vtk_server import VisorVTKServer


@pytest.fixture
def wiring():
    """Build a VisorVTKServer against doubles; yield (app_cls, scene_cls, bridge_cls, mgr, publishers)."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mgr_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.ServerApp") as app_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.VisorServerScene") as scene_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.ServerLoopBridge") as bridge_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.ServerStatePublisher") as publisher_cls:
        mgr = MagicMock()
        mgr.running = False
        mgr_cls.return_value = mgr
        # A distinct bridge per construction, so two bridges cannot pass for one.
        bridge_cls.side_effect = lambda *args, **kwargs: MagicMock(name="bridge")
        # Each publisher built is recorded with its constructor arguments.
        publishers: list[tuple[tuple, MagicMock]] = []

        def build_publisher(*args):
            publishers.append((args, MagicMock(name="publisher")))
            return publishers[-1][1]

        publisher_cls.side_effect = build_publisher
        VisorVTKServer()
        yield app_cls, scene_cls, bridge_cls, mgr, publishers


def test_scene_and_app_share_one_bridge(wiring):
    """The scene's renderer requests frames through the bridge the app binds."""
    app_cls, scene_cls, _bridge_cls, _mgr, _publishers = wiring

    assert scene_cls.call_args.kwargs["bridge"] is app_cls.call_args.kwargs["bridge"]


def test_app_receives_the_scene_members(wiring):
    """The app is given the scene itself, its RCA window, and its pick and theme methods."""
    app_cls, scene_cls, _bridge_cls, _mgr, _publishers = wiring
    scene = scene_cls.return_value
    kwargs = app_cls.call_args.kwargs

    assert kwargs["scene_mutation_api"] is scene
    assert kwargs["rca_window"] is scene.rca_window
    assert kwargs["pick_part_at"] is scene.pick_part_at
    assert kwargs["set_dark_mode"] is scene.set_dark_mode


def test_scene_publishes_camera_into_the_viewer_state(wiring):
    """The scene gets the one publisher, built over this viewer's runner and server state."""
    _app_cls, scene_cls, _bridge_cls, mgr, publishers = wiring

    assert [args for args, _ in publishers] == [(mgr.async_runner, mgr.server.state)]
    assert scene_cls.call_args.kwargs["camera_publisher"] is publishers[0][1]


