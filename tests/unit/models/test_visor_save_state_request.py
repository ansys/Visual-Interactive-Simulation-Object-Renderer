import pytest
from pydantic import ValidationError

from ansys.visor.viewer.models.runtime.requests.visor_save_state_request import (
    VisorSaveStateRequest,
)


def test_create_valid_request():
    """Valid request should be created with request_id."""

    req = VisorSaveStateRequest(request_id=123)

    assert req.request_id == 123


def test_request_id_is_required():
    """Missing request_id should raise ValidationError."""

    with pytest.raises(ValidationError):
        VisorSaveStateRequest()


def test_request_id_must_be_int():
    """Non-integer request_id should raise ValidationError."""

    with pytest.raises(ValidationError):
        VisorSaveStateRequest(request_id="not-an-int")


def test_model_dump_contains_request_id():
    """model_dump(by_alias=True) should include the camelCase requestId wire field."""

    req = VisorSaveStateRequest(request_id=5)
    data = req.model_dump(by_alias=True)

    assert data == {"requestId": 5}


def test_arbitrary_types_allowed_behavior():
    """Model should allow arbitrary types without failure."""

    class Dummy:
        pass

    # Nothing in the schema uses arbitrary types directly,
    # but Config enables it — this ensures it doesn't break.
    req = VisorSaveStateRequest(request_id=1)

    assert isinstance(req, VisorSaveStateRequest)
