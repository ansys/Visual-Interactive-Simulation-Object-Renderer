"""Settings for Visor app."""

import os
from pathlib import Path

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Settings for Visor app.
    """
    app_name: str = "Visor Viewer"
    default_host: str = "localhost"
    default_port: int = 8081
    default_standalone: bool = True
    default_dark_mode: bool = False
    default_client_bundle: str = str(Path(__file__).parent.joinpath("client_bundle"))
    # Log directory resolution order (first match wins):
    #   1. .visor config file  — "default_log_dir: /some/path"
    #   2. GLOW_PROJECT_FILES_DIRECTORY env var — resolves to <GLOW_DIR>/../logs
    #   3. Startup directory fallback — <cwd>/logs
    default_log_dir: str = Field(
        default_factory=lambda: (
            str(Path(os.environ["GLOW_PROJECT_FILES_DIRECTORY"]).parent / "logs")
            if os.environ.get("GLOW_PROJECT_FILES_DIRECTORY")
            else str(Path.cwd() / "logs")
        )
    )
    trame_log_dir: str | None = None
    perf_logging: bool = False  # enable via .visor YAML or by passing Settings(perf_logging=True)
    # Optional externally routed binding host. Read from env once at startup
    # if present; otherwise leave as None to allow per-instance host fallback.
    binding_host: str | None = Field(default_factory=lambda: os.environ.get("GLOW_PRODUCT_BINDING_HOST"))
    # Optional SSL certificate for Trame/wslink in the format "<cert>,<key>".
    ssl_certificate: str | None = None

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            file_secret_settings,
            **kwargs
    ):
        """Customise the settings for Visor app."""
        def visor_file_settings():
            """Read .visor file settings."""
            config_path = Path.cwd() / ".visor"
            if config_path.exists():
                print(f'Loading Visor settings from {config_path}')
                with open(config_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                for key in ["app_name", "default_client_bundle"]:
                    data.pop(key, None)
                return data
            return {}
        return (visor_file_settings, init_settings)

    def get_client_bundle(self, standalone: bool = True) -> str | None:
        """Get the client bundle path based on the standalone flag."""
        if standalone:
            return self.default_client_bundle
        return None

    @model_validator(mode="after")
    def _resolve_ssl_certificate(self) -> "Settings":
        # Normalize empty or whitespace-only strings to None so consumers
        # can rely on ``ssl_certificate`` being either a non-empty string
        # or None. This also avoids truthy non-string values (e.g. MagicMock)
        # from being interpreted as valid certificates.
        if isinstance(self.ssl_certificate, str):
            if not self.ssl_certificate.strip():
                self.ssl_certificate = None
            else:
                return self
        # If a non-string (e.g. MagicMock) was set, coerce to None
        if self.ssl_certificate is not None and not isinstance(self.ssl_certificate, str):
            self.ssl_certificate = None

        # Resolve from environment variables if present
        cert = self._get_ssl_certificate()
        if cert:
            self.ssl_certificate = cert
        return self

    @property
    def url_scheme(self) -> str:
        """Return the URL scheme to advertise: 'https' when a non-empty
        SSL certificate is configured, otherwise 'http'.

        Use this property throughout the codebase instead of duplicating
        the ssl_presence check.
        """
        ssl_val = self.ssl_certificate
        return "https" if isinstance(ssl_val, str) and ssl_val.strip() else "http"

    @staticmethod
    def _get_ssl_certificate() -> str | None:
        certs_dir = os.getenv("GLOW_CERTS_DIR") or os.getenv("ANSYS_GRPC_CERTIFICATES")
        if not certs_dir:
            return None
        p = Path(certs_dir)
        if not p.exists() or not p.is_dir():
            return None
        candidates = [("server.crt", "server.key"), ("client.crt", "client.key")]
        for cert_name, key_name in candidates:
            cert_path = p / cert_name
            key_path = p / key_name
            if cert_path.exists() and key_path.exists():
                return f"{str(cert_path)},{str(key_path)}"
        return None

settings = Settings()
