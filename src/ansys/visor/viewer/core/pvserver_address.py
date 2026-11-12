"""Address of the pvserver a PARAVIEW session connects to."""

from pydantic import BaseModel, ConfigDict, Field


class PvserverAddress(BaseModel):
    """Host and port of the pvserver one PARAVIEW session connects to."""
    model_config = ConfigDict(frozen=True)

    host: str
    port: int = Field(ge=1, le=65535)

    def __str__(self) -> str:
        """host:port, the form every log line and error message uses."""
        return f"{self.host}:{self.port}"
