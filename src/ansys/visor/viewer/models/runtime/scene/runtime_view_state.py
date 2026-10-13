"""Model for the view records the renderer tracks."""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState


class RuntimeViewState(BaseModel):
    """The two records the renderer tracks: camera and plane.

    Neither has a default value: a file that carries either as null leaves the
    server's record as it is, the same as a file that omits it.
    """
    model_config = ConfigDict(populate_by_name=True)

    camera: VisorCameraState | None  # None until the renderer first sets it
    cross_section: VisorCrossSectionState | None = Field(alias="crossSection")  # None until the renderer first sets it


def scene_dump_with_view(scene: Dict[str, Any], view: Dict[str, Any]) -> Dict[str, Any]:
    """A dumped scene record with the dumped view's keys placed directly after ``unit``.

    The wire carries the camera and the plane inside the scene object, not
    under a key of their own; this rebuilds that shape from the two dumps.
    """
    out: Dict[str, Any] = {}
    for key, value in scene.items():
        out[key] = value
        if key == "unit":
            out.update(view)
    return out
