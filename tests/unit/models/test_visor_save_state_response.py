import json
from unittest.mock import MagicMock, patch

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
    """Rewritten in place (3.5.1 increment 1): the save path no longer rejects this entry.

    The server owns the variable records, so the browser's ``variableStates`` is
    discarded before validation.  An entry missing the identity fields (an old
    client) therefore parses, and nothing of it reaches the model.
    """
    payload = {
        "requestId": 1,
        "appState": {
            "scene": {
                "variableStates": {
                    "POINT::pressure::1": {
                        "id": "POINT::pressure::1",
                        "magnitudeRange": [0.0, 1.0],
                        "ranges": [[0.0, 1.0]],
                    }
                }
            }
        },
    }

    resp = VisorSaveStateResponse.model_validate(payload)

    assert resp.app_state.scene.variable_states == {}


def test_save_path_accepts_a_variable_state_carrying_the_identity_fields():
    """Rewritten in place (3.5.1 increment 1): a complete browser entry is discarded too."""
    payload = {
        "requestId": 1,
        "appState": {
            "scene": {
                "variableStates": {
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

    assert resp.app_state.scene.variable_states == {}


def test_save_response_discards_browser_variable_states_from_a_json_string_app_state():
    """#21: the discard also runs when appState arrives as a JSON string, and logs one DEBUG line.

    The entry lacks the record's default fields (partIds, defaultMagnitudeRange,
    defaultRanges), so without the discard it would fail validation against the record.
    """
    app_state = json.dumps({
        "scene": {
            "unit": "mm",
            "variableStates": {
                "POINT::pressure::1": {
                    "id": "POINT::pressure::1",
                    "arrayName": "pressure",
                    "type": "POINT",
                    "numComponents": 1,
                    "magnitudeRange": [0.0, 1.0],
                    "ranges": [[0.0, 1.0]],
                }
            },
        }
    })

    with patch("ansys.visor.viewer.models.runtime.requests.visor_save_state_response.logger") as mock_logger:
        resp = VisorSaveStateResponse.model_validate({"requestId": 7, "appState": app_state})

    assert resp.app_state.scene.variable_states == {}
    assert resp.app_state.scene.unit == "mm"
    mock_logger.debug.assert_called_once_with("browser variableStates discarded")

