from ansys.visor.viewer.models.runtime.visor_scene_details import VisorSceneDetails


def test_scene_details_has_no_view_field():
    """The details carry the UI and scene records beside the VTK info, and no view."""
    assert set(VisorSceneDetails.model_fields) == {"schema_version", "ui", "scene", "vtk_info"}
