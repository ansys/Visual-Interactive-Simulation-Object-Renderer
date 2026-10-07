import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState


class VisorSaveStateResponse(BaseModel):
    """
    Model for the response from the client to receive the runtime
    viewer state, which is in turn used by the server to save the persisted state of the
    Visor viewer.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # A unique identifier for the load state request.
    request_id: int = Field(alias="requestId")
    app_state: RuntimeAppState = Field(alias="appState")

    @field_validator("app_state", mode="before")
    @classmethod
    def _coerce_app_state(cls, v: Any) -> Any:
        """Coerce the app_state value to an Any type, allowing for flexible input formats."""
        # Accept already-built model
        if isinstance(v, RuntimeAppState):
            return v

        # Accept JSON string
        if isinstance(v, str):
            v = json.loads(v)

        # Accept dict and let Pydantic recursively build RuntimeAppState + nested models
        if isinstance(v, dict):
            return RuntimeAppState.model_validate(v)

        return v
