"""Model for UI state in a Visor visualization."""

from pydantic import BaseModel, ConfigDict, Field


class VisorUIState(BaseModel):
    """
    Represents the UI state of a Visor visualization, such as theme preference.
    """
    model_config = ConfigDict(populate_by_name=True)

    dark_theme: bool | None = Field(default=None, alias="darkTheme")
    panel_top_left_panel_collapsed: bool | None = Field(default=None, alias="panelTopLeftPanelCollapsed")
    panel_top_right_panel_collapsed: bool | None = Field(default=None, alias="panelTopRightPanelCollapsed")
    panel_top_right_legend_collapsed: bool | None = Field(default=None, alias="panelTopRightLegendCollapsed")
    panel_top_right_tab_index: int | None = Field(default=None, alias="panelTopRightTabIndex")
