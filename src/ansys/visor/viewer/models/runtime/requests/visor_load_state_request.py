"""Model for loading a Visor viewer state."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.models.runtime.scene.runtime_view_state import scene_dump_with_view


class VisorLoadStateRequest(BaseModel):
    """
    Request model for loading a Visor viewer state.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # A unique identifier for the load state request.
    request_id: int
    app_state: RuntimeAppState = Field(alias="appState")

    @model_serializer(mode="wrap")
    def _dump_in_the_flat_scene_shape(
            self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict:
        """Move the view's camera and crossSection into appState.scene after unit; emit no view key."""
        data: dict = handler(self)
        app_key = "appState" if info.by_alias else "app_state"
        app_state: dict = data[app_key]
        view: dict = app_state.pop("view")
        app_state["scene"] = scene_dump_with_view(app_state["scene"], view)
        return data
