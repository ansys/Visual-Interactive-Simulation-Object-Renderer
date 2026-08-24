"""
tests/unit/app/test_visor_vtk.py
=================================
Tests for VisorVTK.__new__ dispatch and abstract-method contract.

Lifecycle behaviour is covered by test_visor_vtk_local.py; nothing here
starts a trame server.  Mocking boundary is identical to that file:
  - ansys.visor.viewer.app.visor_vtk.TrameServerManager
  - ansys.visor.viewer.app.visor_vtk_local.LocalApp
  - ansys.visor.viewer.app.visor_vtk_local.VisorLocalScene
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.app.visor_vtk_local import VisorVTKLocal
from ansys.visor.viewer.core.visor_enums import RenderingMode

MODE_TO_CLASS = [
    pytest.param(RenderingMode.LOCAL, VisorVTKLocal, id="LOCAL"),
]


@contextmanager
def vtk_patches():
    """Suppress all trame / VTK side-effects so no server is started."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mock_mgr, \
         patch("ansys.visor.viewer.app.visor_vtk_local.LocalApp"), \
         patch("ansys.visor.viewer.app.visor_vtk_local.VisorLocalScene") as mock_scene:
        mock_mgr_inst = MagicMock()
        mock_mgr_inst.running = False
        mock_scene_inst = MagicMock()
        mock_scene_inst.datasets = {}
        mock_scene.return_value = mock_scene_inst
        mock_mgr.return_value = mock_mgr_inst
        yield mock_mgr, mock_scene


def make_vtk(**kwargs) -> VisorVTK:
    """Convenience wrapper: enter vtk_patches and return a VisorVTK instance."""
    with vtk_patches():
        return VisorVTK(**kwargs)


@pytest.mark.parametrize("mode,expected_cls", MODE_TO_CLASS)
def test_dispatch_returns_correct_subclass(mode, expected_cls):
    """VisorVTK(rendering_mode=<mode>) returns an instance of expected_cls."""
    with vtk_patches():
        inst = VisorVTK(rendering_mode=mode)
    assert isinstance(inst, expected_cls)


def test_init_called_once_with_original_args():
    """__init__ is invoked exactly once, forwarding the original call-site kwargs."""
    with vtk_patches():
        with patch.object(VisorVTK, "__init__", return_value=None) as mock_init:
            VisorVTK(rendering_mode=RenderingMode.LOCAL, url="http://test", standalone=False)

    mock_init.assert_called_once()
    _, kwargs = mock_init.call_args
    assert kwargs.get("rendering_mode") == RenderingMode.LOCAL
    assert kwargs.get("url") == "http://test"
    assert kwargs.get("standalone") is False


def test_direct_construction_no_recursion():
    """VisorVTKLocal() constructed directly never re-enters VisorVTK.__new__ dispatch."""
    with vtk_patches():
        with patch.object(VisorVTK, "__init__", return_value=None) as mock_init:
            inst = VisorVTKLocal()

    assert type(inst) is VisorVTKLocal
    mock_init.assert_called_once()


def test_unrecognized_mode_raises_value_error():
    """A mode not present in the mode_map raises ValueError naming the bad mode."""
    sentinel = MagicMock(name="FAKE_MODE")

    with patch(
        "ansys.visor.viewer.app.visor_vtk.RenderingMode.from_string",
        return_value=sentinel,
    ):
        with pytest.raises(ValueError, match="Unsupported rendering mode for VTK"):
            VisorVTK(rendering_mode=sentinel)


def test_default_rendering_mode_dispatches_to_local():
    """VisorVTK() with no rendering_mode argument falls back to LOCAL."""
    with vtk_patches():
        inst = VisorVTK()
    assert isinstance(inst, VisorVTKLocal)


def test_abstract_method_not_implemented_raises():
    """A VisorVTK subclass that omits _initialize_rendering leaves the instance
    without ``_scene``.  VisorVTK does not use ABCMeta (as proven by the
    existing DummyIface fixture in test_visor_vtk_local.py), so Python does
    not raise TypeError at instantiation time.  The *intended* failure instead
    surfaces as AttributeError the moment any caller tries to use ``_scene``,
    because ``_initialize_rendering`` never ran to create it.
    """

    class _Incomplete(VisorVTK):
        pass  # deliberately does NOT implement _initialize_rendering

    with vtk_patches():
        inst = _Incomplete()

    # _initialize_rendering was never called with a real body, so _scene is absent.
    with pytest.raises(AttributeError):
        _ = inst._scene  # noqa: F841

