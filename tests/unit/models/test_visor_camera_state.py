import pytest
from pydantic import ValidationError

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState


def test_valid_camera_state():
    """Verify that a valid VisorCameraState is created successfully."""
    cam = VisorCameraState(
        position=[1.0, 2.0, 3.0],
        focal_point=[0.0, 0.0, 0.0],
        view_up=[0.0, 1.0, 0.0],
        clipping_range=[0.1, 1000.0],
        parallel_projection=True,
        view_angle=30.0,
        parallel_scale=1.5,
    )

    assert cam.position == [1.0, 2.0, 3.0]
    assert cam.focal_point == [0.0, 0.0, 0.0]
    assert cam.view_up == [0.0, 1.0, 0.0]
    assert cam.clipping_range == [0.1, 1000.0]
    assert cam.parallel_projection is True
    assert isinstance(cam.view_angle, float) and cam.view_angle == 30.0
    assert isinstance(cam.parallel_scale, float) and cam.parallel_scale == 1.5


def test_missing_required_field_raises():
    """Verify that missing required field raises ValidationError."""
    # omit 'position' which is required
    with pytest.raises(ValidationError):
        VisorCameraState(
            focal_point=[0.0, 0.0, 0.0],
            view_up=[0.0, 1.0, 0.0],
            clipping_range=[0.1, 1000.0],
            parallel_projection=False,
            view_angle=45.0,
            parallel_scale=2.0,
        )


def test_invalid_element_type_in_list_raises():
    """Verify that invalid element type raises ValidationError."""
    # a non-float element in the position list should cause validation to fail
    with pytest.raises(ValidationError):
        VisorCameraState(
            position=[1.0, 'bad', 3.0],
            focal_point=[0.0, 0.0, 0.0],
            view_up=[0.0, 1.0, 0.0],
            clipping_range=[0.1, 1000.0],
            parallel_projection=False,
            view_angle=45.0,
            parallel_scale=2.0,
        )


def test_type_coercion_from_tuples_and_ints():
    """Verify that pydantic coerces tuples to lists and ints to floats where appropriate."""
    # pydantic should coerce tuples to lists and ints to floats where appropriate
    cam = VisorCameraState(
        position=(1, 2, 3),
        focal_point=(0, 0, 0),
        view_up=(0, 1, 0),
        clipping_range=(1, 200),
        parallel_projection=0,  # falsy int should be accepted as bool-ish
        view_angle=60,  # int -> float
        parallel_scale=4,  # int -> float
    )

    assert cam.position == [1, 2, 3]
    assert cam.focal_point == [0, 0, 0]
    assert cam.view_up == [0, 1, 0]
    assert cam.clipping_range == [1, 200]
    # pydantic will coerce 0 to False for a bool field
    assert cam.parallel_projection is False
    assert isinstance(cam.view_angle, float) and cam.view_angle == 60.0
    assert isinstance(cam.parallel_scale, float) and cam.parallel_scale == 4.0
