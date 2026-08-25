"""Tests for VisorSceneBase as an abstract class.

These tests only assert the abstract contract of VisorSceneBase:
  1. Direct instantiation raises TypeError.
  2. Exactly the expected set of abstract methods is declared.

Behavioural coverage of shared logic lives in test_local_scene.py, exercised
through the concrete VisorLocalScene subclass.
"""
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase


def test_cannot_instantiate_directly():
    """VisorSceneBase is abstract and must raise TypeError on direct instantiation."""
    try:
        VisorSceneBase(None)  # type: ignore[abstract]
        raise AssertionError("Expected TypeError was not raised")
    except TypeError:
        pass


def test_abstract_methods():
    """VisorSceneBase declares exactly the two expected abstract hooks."""
    assert VisorSceneBase.__abstractmethods__ == {
        "_get_runtime_state_async",
        "_apply_runtime_state_to_render",
    }

