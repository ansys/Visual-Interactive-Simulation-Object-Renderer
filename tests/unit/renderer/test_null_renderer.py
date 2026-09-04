"""
Unit tests for NullRenderer's camera record.

NullRenderer owes the *record* half of the IRenderer camera contract in full,
and the *projection* half not at all -- there is no pipeline camera to project
onto.  It also carries the one documented divergence from "every server-side
camera mutation writes the record": ``reset_camera`` leaves the record alone.

That divergence is the reason this module exists.  It is stated in prose in
two places and, before this module, asserted in none; a future edit that made
``reset_camera`` clear the record would have passed every gate in the tree.
"""

from __future__ import annotations

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.null_renderer import NullRenderer

BOUNDS = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def _camera_state() -> VisorCameraState:
    """A camera built from hand-written literals.

    The values are arbitrary but fixed, and none is a vtkCamera construction
    default -- NullRenderer has no vtkCamera, but keeping the literals
    distinctive means a value arriving from anywhere other than this function
    is visible.
    """
    return VisorCameraState(
        position=[1.0, 2.0, 3.0],
        focal_point=[4.0, 5.0, 6.0],
        view_up=[0.0, 0.0, 1.0],
        clipping_range=[7.0, 8.0],
        parallel_projection=False,
        view_angle=31.0,
        parallel_scale=9.0,
    )


# ===========================================================================
# The record
# ===========================================================================

def test_get_camera_state_returns_none_initially():
    """A fresh renderer has no record."""
    assert NullRenderer().get_camera_state() is None


def test_sync_camera_stores_state_for_get():
    """The record half is owed in full, and stores without copying."""
    renderer = NullRenderer()
    cam = _camera_state()

    renderer.sync_camera(cam)

    assert renderer.get_camera_state() is cam


# ===========================================================================
# The documented divergence: reset_camera does not write the record
# ===========================================================================

def test_reset_camera_does_not_clear_a_synced_record():
    """A reset must not destroy a camera the frontend reported.

    With no pipeline camera there is nothing from which to derive a camera for
    *bounds*, so the record keeps its previous value rather than being
    cleared.  Object identity, so a rebuild-from-values would fail too.
    """
    renderer = NullRenderer()
    cam = _camera_state()
    renderer.sync_camera(cam)

    renderer.reset_camera(BOUNDS)

    assert renderer.get_camera_state() is cam


def test_reset_camera_on_a_fresh_renderer_leaves_the_record_none():
    """Leaving the record alone means leaving it None when it was None."""
    renderer = NullRenderer()

    renderer.reset_camera(BOUNDS)

    assert renderer.get_camera_state() is None


def test_each_renderer_has_its_own_record():
    """The record is instance state, not shared on the class."""
    first = NullRenderer()
    second = NullRenderer()

    first.sync_camera(_camera_state())

    assert first.get_camera_state() is not None
    assert second.get_camera_state() is None


