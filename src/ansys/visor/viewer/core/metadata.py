"""Metadata model for providing information about the dataset to the visualizer."""

from pydantic import BaseModel, Field, ValidationError, model_validator

from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState


class Metadata(BaseModel):
    name: str
    unit: str
    state: PersistedDatasetState = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_state(self) -> "Metadata":
        if not isinstance(self.state, PersistedDatasetState):
            try:
                self.state = PersistedDatasetState.model_validate(self.state)
            except ValidationError:
                raise
        return self


class ExtendedMetadata(Metadata):
    file_path: str | None = None
    metadata_path: str | None = None
