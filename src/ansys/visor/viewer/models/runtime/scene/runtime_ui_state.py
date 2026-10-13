"""Model for the server's UI record."""

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.persist.visor_ui_state import PersistedUIState
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimePartProperties


class RuntimeUIState(BaseModel):
    """The server's UI record, every field required."""
    model_config = ConfigDict(populate_by_name=True)

    dark_theme: bool = Field(alias="darkTheme")
    panel_top_left_panel_collapsed: bool = Field(alias="panelTopLeftPanelCollapsed")
    panel_top_right_panel_collapsed: bool = Field(alias="panelTopRightPanelCollapsed")
    panel_top_right_legend_collapsed: bool = Field(alias="panelTopRightLegendCollapsed")
    panel_top_right_tab_index: int = Field(alias="panelTopRightTabIndex")

    def overlaid_with(self, persisted: PersistedUIState, defaults: "RuntimeUIState") -> "RuntimeUIState":
        """A new record: a field the file names takes its value, or the default where null; an unnamed field
        keeps this record's.  This record is not modified."""
        return type(self)(**{
            field: RuntimePartProperties._overlaid(
                getattr(self, field), persisted, field, getattr(defaults, field)
            )
            for field in type(self).model_fields
        })

    def to_persisted(self) -> PersistedUIState:
        """The persisted record carrying all five values."""
        return PersistedUIState(**{field: getattr(self, field) for field in type(self).model_fields})
