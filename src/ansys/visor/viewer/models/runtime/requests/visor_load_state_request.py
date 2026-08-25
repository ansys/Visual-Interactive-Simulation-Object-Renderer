"""Model for loading a Visor viewer state."""

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState


class VisorLoadStateRequest(BaseModel):
    """
    Request model for loading a Visor viewer state.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # A unique identifier for the load state request.
    request_id: int
    app_state: RuntimeAppState = Field(alias="appState")
