"""
Unit tests for NullRenderer's camera record.

NullRenderer owes the *record* half of the IRenderer camera contract in full,
and the *projection* half not at all -- there is no pipeline camera to project
onto.  It also carries the one documented divergence from "every server-side
camera mutation writes the record": ``reset_camera`` leaves the record alone.
"""

from __future__ import annotations

from unittest.mock import patch

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


# ===========================================================================
# Publishing is not recording
# ===========================================================================

def test_serialize_camera_state_is_a_no_op_and_leaves_the_record_alone():
    """This renderer serves the client nothing, so it has nothing to refresh.

    Two things are asserted together because the method has exactly two ways
    to be wrong here.  It must not raise -- a bare ``pass`` inherited by
    accident would satisfy that alone -- and it must not touch the record.
    Publishing and recording are separate obligations: the writers of the
    record are ``reset_camera`` and ``sync_camera``, and this is neither.  An
    implementation that cleared the record on serialise would be a silent data
    loss on the renderer used to stand in for a second backend, and no other
    test in the tree would notice.
    """
    renderer = NullRenderer()
    cam = _camera_state()
    renderer.sync_camera(cam)

    renderer.serialize_camera_state()

    assert renderer.get_camera_state() is cam


# ===========================================================================
# Projection: the record half owed in full, the pipeline half not at all
# ===========================================================================

def test_set_projection_writes_the_record_in_place_preserving_identity():
    """The record is mutated, not replaced, exactly as on the local renderer.

    The record half of the projection contract is not optional on any
    implementation.  Identity is asserted as well as value because callers
    rely on object identity through ``get_camera_state``, and a body that
    rebuilt the record would satisfy the value assertion alone.

    The seed carries the literal ``False`` so the write is a transition.
    """
    renderer = NullRenderer()
    cam = _camera_state()
    renderer.sync_camera(cam)

    renderer.set_projection(True)

    assert renderer.get_camera_state() is cam
    assert cam.parallel_projection is True


def test_set_projection_with_no_record_is_a_logged_no_op():
    """With no record there is nothing to write, and nothing to project onto.

    This renderer has no pipeline camera, so unlike the local renderer there
    is no second half to fall through to: the whole method is the record, and
    an empty record makes the whole method a logged no-op.  Asserted as "still
    ``None``" rather than "did not raise", because a body that seeded a record
    here would also not raise.
    """
    renderer = NullRenderer()

    with patch("ansys.visor.viewer.renderer.null_renderer.logger") as log:
        renderer.set_projection(True)

    assert renderer.get_camera_state() is None
    assert log.debug.call_count == 1



