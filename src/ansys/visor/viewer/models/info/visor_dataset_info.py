"""Info for a Visor dataset."""

from pydantic import BaseModel, Field


class VisorDatasetInfo(BaseModel):
    """
    Info for a Visor dataset.
    """
    id: int = Field(...)
    name: str = Field(...)
    unit: str = Field(...)
    file_path: str | None = None
    metadata_path: str | None = None

