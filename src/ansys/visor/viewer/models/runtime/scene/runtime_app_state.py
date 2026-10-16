"""Model for the runtime application state for a Visor visualizer instance."""

from pydantic import BaseModel, ConfigDict

from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState
from ansys.visor.viewer.models.runtime.scene.runtime_ui_state import RuntimeUIState
from ansys.visor.viewer.models.runtime.scene.runtime_view_state import RuntimeViewState


class RuntimeAppState(BaseModel):
    """The save and load carrier: ui, scene, view.

    Each record has one owner on the server: the UI record and the scene
    record are the scene coordinator's, the view records are the renderer's.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    ui: RuntimeUIState
    view: RuntimeViewState
    scene: RuntimeSceneState
