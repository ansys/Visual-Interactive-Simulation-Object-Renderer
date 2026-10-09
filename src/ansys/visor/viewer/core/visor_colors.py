"""Class defining colors used in Visor"""

class VisorColors:
    """Default colors used in Visor Viewer."""
    BackgroundColor: tuple[float, float, float] = (0,0,0) # <-- keep this at 0,0,0 to allow for color changes on the frontend with CSS
    DefaultMeshColor: tuple[float, float, float] = (0.8, 0.8, 0.8)
    DefaultSelectionColor: tuple[float, float, float] = (0.184, 0.427, 0.620)
    DefaultSelectedMeshEdgeColor: tuple[float, float, float] = (0, 0, 0)


class VisorPartDefaults:
    """Values a part record holds for a property nothing has set."""
    Visible: bool = True
    Opacity: float = 1.0
    Selected: bool = False
    DiffuseRgb: tuple[float, float, float] = VisorColors.DefaultMeshColor

