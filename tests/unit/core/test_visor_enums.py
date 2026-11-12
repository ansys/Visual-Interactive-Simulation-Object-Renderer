from ansys.visor.viewer.core.visor_enums import RenderingMode


def test_rendering_mode_from_string_paraview():
    """Verify that the PARAVIEW mode is found by its case-insensitive name."""
    assert RenderingMode.from_string("paraview") is RenderingMode.PARAVIEW


def test_rendering_mode_paraview_wire_value():
    """Verify the value the frontend receives for the PARAVIEW mode."""
    assert RenderingMode.PARAVIEW.value == "paraview"
