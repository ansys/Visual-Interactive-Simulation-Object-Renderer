import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState

logger = VisorDefaultLogger(__name__)


class VisorSaveStateResponse(BaseModel):
    """
    Model for the response from the client to receive the runtime
    viewer state, which is in turn used by the server to save the persisted state of the
    Visor viewer.

    The server owns the variable records, so any ``appState.scene.variableStates`` the
    browser sends is discarded before validation (see :meth:`_discard_browser_variable_states`).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # A unique identifier for the load state request.
    request_id: int = Field(alias="requestId")
    app_state: RuntimeAppState = Field(alias="appState")

    # Guards a client that still sends variableStates in the pre-record shape.
    @model_validator(mode="before")
    @classmethod
    def _discard_browser_variable_states(cls, data: Any) -> Any:
        """Drop ``appState.scene.variableStates`` from the browser's reply.

        The browser's entries lack the record's default fields and are not the
        authority; ``get_state`` takes the variables from the server's record.
        """
        if not isinstance(data, dict):
            return data
        key = "appState" if "appState" in data else ("app_state" if "app_state" in data else None)
        if key is None:
            return data
        app_state = data[key]
        if isinstance(app_state, str):
            try:
                app_state = json.loads(app_state)
            except (TypeError, ValueError):
                return data
        if not isinstance(app_state, dict):
            return data
        scene = app_state.get("scene")
        if not isinstance(scene, dict):
            return data
        discarded = False
        for scene_key in ("variableStates", "variable_states"):
            if scene_key in scene:
                discarded = True
        if not discarded:
            return data
        scene = {k: v for k, v in scene.items() if k not in ("variableStates", "variable_states")}
        logger.debug("browser variableStates discarded")
        return {**data, key: {**app_state, "scene": scene}}

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
