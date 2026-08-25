"""Model for sending a request to the client to retrieve the runtime viewer state."""

from pydantic import BaseModel, ConfigDict, Field


class VisorSaveStateRequest(BaseModel):
    """
    Model for sending a request to the client to retrieve the runtime
    viewer state, which is in turn used by the server to save the persisted state of the
    Visor viewer.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # A unique identifier for the load state request.
    request_id: int = Field(alias="requestId")
