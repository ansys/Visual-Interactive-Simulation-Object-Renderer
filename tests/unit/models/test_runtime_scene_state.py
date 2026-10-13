from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_variable_record import VisorVariableRecord
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
)
from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import (
    RuntimeSceneState,
)

# ------------------------------------------------------------------
# dataset_states validator
# ------------------------------------------------------------------

def test_dataset_states_none_becomes_empty():
    """None dataset_states should be coerced to empty dict."""

    state = RuntimeSceneState(dataset_states=None)

    assert state.dataset_states == {}


def test_dataset_states_coerce_string_keys_to_int():
    """String keys should be coerced to int."""

    data = {
        "1": MagicMock(spec=RuntimeDatasetState),
        "2": MagicMock(spec=RuntimeDatasetState),
    }

    state = RuntimeSceneState(dataset_states=data)

    assert set(state.dataset_states.keys()) == {1, 2}


def test_dataset_states_invalid_keys_raise():
    """Invalid keys should fail validation."""

    data = {
        "bad": MagicMock(spec=RuntimeDatasetState),
    }

    with pytest.raises(ValidationError):
        RuntimeSceneState(dataset_states=data)


def test_dataset_states_passthrough_non_dict():
    """Non-dict dataset_states should fail validation."""

    with pytest.raises(ValidationError):
        RuntimeSceneState(dataset_states=123)


# ------------------------------------------------------------------
# general model behavior
# ------------------------------------------------------------------

def test_default_fields():
    """Default construction should initialize expected defaults."""

    state = RuntimeSceneState()

    assert state.dataset_states == {}
    assert state.variable_states == {}
    assert state.unit is None


def test_setting_basic_fields():
    """Basic fields should be stored correctly."""

    state = RuntimeSceneState(
        unit="m",
        orthographic_enabled=True,
        edges_enabled=False,
    )

    assert state.unit == "m"
    assert state.orthographic_enabled is True
    assert state.edges_enabled is False


def test_dataset_states_accept_valid_mapping():
    """Valid dataset_states should be accepted."""

    data = {
        "1": MagicMock(spec=RuntimeDatasetState),
    }

    state = RuntimeSceneState(dataset_states=data)

    assert 1 in state.dataset_states
    assert isinstance(state.dataset_states[1], RuntimeDatasetState)


# ------------------------------------------------------------------
# variable_states
# ------------------------------------------------------------------

def test_variable_states_default_and_assignment():
    """variable_states holds the server's records: a real record built from literals."""

    record = VisorVariableRecord(
        id="POINT::pressure::1",
        array_name="pressure",
        type=VisorVtkVariableType.POINT,
        num_components=1,
        part_ids=[1],
        default_magnitude_range=(0.0, 10.0),
        default_ranges=[(0.0, 10.0)],
        magnitude_range=(2.0, 3.0),
        ranges=[(2.0, 3.0)],
    )

    state = RuntimeSceneState(variable_states={"POINT::pressure::1": record})

    stored = state.variable_states["POINT::pressure::1"]
    assert isinstance(stored, VisorVariableRecord)
    assert stored.magnitude_range == (2.0, 3.0)
    assert stored.default_ranges == [(0.0, 10.0)]
    assert stored.part_ids == [1]
