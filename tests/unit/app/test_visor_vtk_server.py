"""Unit tests for ``VisorVTKServer``'s wiring of the bridge, the server scene
and ``ServerApp``.

Mocking boundary: ``visor_vtk.TrameServerManager``,
``visor_vtk_server.ServerApp``, ``visor_vtk_server.VisorServerScene`` and
``visor_vtk_server.ServerLoopBridge``.  Nothing here starts a trame server.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.visor_vtk_server import VisorVTKServer


@pytest.fixture
def wiring():
    """Build a VisorVTKServer against doubles; yield (app_cls, scene_cls, bridge_cls)."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mgr_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.ServerApp") as app_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.VisorServerScene") as scene_cls, \
         patch("ansys.visor.viewer.app.visor_vtk_server.ServerLoopBridge") as bridge_cls:
        mgr = MagicMock()
        mgr.running = False
        mgr_cls.return_value = mgr
        # A distinct bridge per construction, so two bridges cannot pass for one.
        bridge_cls.side_effect = lambda *args, **kwargs: MagicMock(name="bridge")
        VisorVTKServer()
        yield app_cls, scene_cls, bridge_cls


def test_scene_and_app_share_one_bridge(wiring):
    """The scene's renderer requests frames through the bridge the app binds."""
    app_cls, scene_cls, _bridge_cls = wiring

    assert scene_cls.call_args.kwargs["bridge"] is app_cls.call_args.kwargs["bridge"]


def test_app_receives_the_scene_members(wiring):
    """The app is given the scene itself, its RCA window, and its pick and theme methods."""
    app_cls, scene_cls, _bridge_cls = wiring
    scene = scene_cls.return_value
    kwargs = app_cls.call_args.kwargs

    assert kwargs["scene_mutation_api"] is scene
    assert kwargs["rca_window"] is scene.rca_window
    assert kwargs["pick_part_at"] is scene.pick_part_at
    assert kwargs["set_dark_mode"] is scene.set_dark_mode

