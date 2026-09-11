"""Model for the ``sync_camera`` trigger payload."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState


class SyncCameraPayload(BaseModel):
    """
    Payload of the ``sync_camera`` trigger.

    ``origin`` travels on the wire and the server decides what to do with it:
    the client sends both values and never suppresses a report it believes is
    an echo.  A report the server drops is visible in the log when diagnosing
    an echo; one the client never sent is not.

    ``camera`` is a whole :class:`VisorCameraState` -- whole or absent, never
    partial.  All seven fields are required with no default, so a payload
    missing any one of them fails validation and is a logged no-op at the
    trigger boundary rather than a half-applied camera.

    Extra keys are ignored, which is deliberate rather than incidental: the
    client's own camera snapshot type carries five derived display fields
    (``distance``, ``orthographic``, ``orthographicScale``, ``unitsPerPixel``,
    ``viewPortHeight``) beyond the seven applied ones, and a sender that
    spread that whole object would still validate here.  What pins the wire
    shape is therefore a test on the payload the client builds, not this
    model.
    """

    model_config = ConfigDict(populate_by_name=True)

    origin: Literal["gesture", "programmatic"]
    camera: VisorCameraState

