import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ansys.visor.viewer.models.runtime.requests.visor_save_state_response import (
    VisorSaveStateResponse,
)
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_runtime_state():
    """Create a RuntimeAppState-compatible mock."""
    return MagicMock(spec=RuntimeAppState)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_create_response_from_dict(monkeypatch):
    """Dict app_state should be converted via model_validate."""

    monkeypatch.setattr(
        RuntimeAppState,
        "model_validate",
        lambda data: make_runtime_state(),
    )

    resp = VisorSaveStateResponse(request_id=2, app_state={"x": 10})

    assert isinstance(resp.app_state, RuntimeAppState)


def test_create_response_from_json_string(monkeypatch):
    """JSON string app_state should be parsed and validated."""

    monkeypatch.setattr(
        RuntimeAppState,
        "model_validate",
        lambda data: make_runtime_state(),
    )

    data = json.dumps({"foo": "bar"})

    resp = VisorSaveStateResponse(request_id=3, app_state=data)

    assert isinstance(resp.app_state, RuntimeAppState)


def test_create_valid_response_with_model_passthrough():
    """Already-constructed RuntimeAppState should pass through unchanged."""

    existing = make_runtime_state()

    resp = VisorSaveStateResponse(request_id=1, app_state=existing)

    assert resp.app_state is existing


def test_invalid_request_id_raises():
    """Non-integer request_id should raise ValidationError."""

    with pytest.raises(ValidationError):
        VisorSaveStateResponse(request_id="bad", app_state={})


def test_missing_app_state_raises():
    """Missing app_state should raise ValidationError."""

    with pytest.raises(ValidationError):
        VisorSaveStateResponse(request_id=1)


def test_invalid_json_string_raises(monkeypatch):
    """Invalid JSON string should raise during parsing."""

    monkeypatch.setattr(
        RuntimeAppState,
        "model_validate",
        lambda data: make_runtime_state(),
    )

    with pytest.raises(Exception):
        VisorSaveStateResponse(request_id=1, app_state="not-json")


def test_invalid_type_for_app_state_raises():
    """Unexpected app_state type should fail validation."""

    with pytest.raises(ValidationError):
        VisorSaveStateResponse(request_id=1, app_state=123)


def test_model_dump_contains_fields(monkeypatch):
    """model_dump(by_alias=True) should include the expected camelCase wire fields."""

    dummy = make_runtime_state()

    monkeypatch.setattr(
        RuntimeAppState,
        "model_validate",
        lambda data: dummy,
    )

    resp = VisorSaveStateResponse(request_id=5, app_state={"k": "v"})
    data = resp.model_dump(by_alias=True)

    assert data["requestId"] == 5
    assert "appState" in data


def test_save_path_rejects_a_variable_state_missing_the_identity_fields():
    """The save path must keep raising on a client that stops emitting the fields.

    ``VisorVariableState`` is shared between ``PersistedSceneState.variable_states``
    and ``RuntimeSceneState.spectrum_states``, so making the three identity
    fields optional on the model would have relaxed this coercion too.  The
    tolerance for old save files lives on the persisted container instead, and
    this pins the fact that it did not leak here: reads tolerate absence,
    writes do not.
    """
    payload = {
        "requestId": 1,
        "appState": {
            "scene": {
                "spectrumStates": {
                    "POINT::pressure::1": {
                        "id": "POINT::pressure::1",
                        "magnitudeRange": [0.0, 1.0],
                        "ranges": [[0.0, 1.0]],
                    }
                }
            }
        },
    }

    with pytest.raises(ValidationError) as excinfo:
        VisorSaveStateResponse.model_validate(payload)

    # Reported under the wire alias, which is the spelling validation ran by.
    reported = {error["loc"][-1] for error in excinfo.value.errors()}
    assert {"arrayName", "type", "numComponents"} <= reported


def test_save_path_accepts_a_variable_state_carrying_the_identity_fields():
    """The same payload with the three fields present validates, so the guard is specific."""
    payload = {
        "requestId": 1,
        "appState": {
            "scene": {
                "spectrumStates": {
                    "POINT::pressure::1": {
                        "id": "POINT::pressure::1",
                        "arrayName": "pressure",
                        "type": "POINT",
                        "numComponents": 1,
                        "magnitudeRange": [0.0, 1.0],
                        "ranges": [[0.0, 1.0]],
                    }
                }
            }
        },
    }

    resp = VisorSaveStateResponse.model_validate(payload)

    stored = resp.app_state.scene.spectrum_states["POINT::pressure::1"]
    assert stored.array_name == "pressure"
    assert stored.num_components == 1

