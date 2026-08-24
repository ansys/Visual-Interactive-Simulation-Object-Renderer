"""Cache for Visor visualizer instances for FastAPI service"""

from typing import Dict, Tuple

from ansys.visor.viewer import Visor
from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import VisorLogger

logger = VisorLogger(__name__, "server.log")


class VisorCache:
    """A simple cache to store Visor instances by URL."""
    _instances: Dict[str, Visor] = {}

    @classmethod
    def get_instance(cls,
                     url: str,
                     rendering_mode: RenderingMode,
                     standalone: bool,
                     dark_mode: bool,
                     trame_log_dir: str | None = None,
                     ) -> Tuple["Visor", str | None]:
        """Get an instance of Visor from the cache or create a new one.

        Returns
        -------
        tuple[Visor, list[str], bool]
            The Visor instance, a list of warning messages for any params
            that were ignored because the instance already existed, and a
            boolean indicating whether a new instance was created.
        """
        if url not in cls._instances:
            msg = (
                f"Visor instance not found on url {url}.  "
                f"Creating a new one with rendering_mode={rendering_mode},"
                f"standalone={standalone},"
                f"dark_mode={dark_mode}, trame_log_dir={trame_log_dir}."
            )
            logger.warning(msg)
            cls.create_instance(url, rendering_mode, standalone, dark_mode, trame_log_dir)
            instance = cls._instances[url]
            if instance is None:
                raise Exception(f"Failed to create Visor instance for url {url}.")
            return instance, None

        warnings = cls.validate_args(url, rendering_mode, standalone, dark_mode, trame_log_dir)
        return cls._instances.get(url), warnings

    @classmethod
    def validate_args(
            cls,
            url: str,
            rendering_mode: RenderingMode,
            standalone: bool,
            dark_mode: bool,
            trame_log_dir: str
        ) -> str:
        """Validate the arguments for this instance."""
        warnings = None
        existing = cls._instances[url]
        ignored = []
        if rendering_mode is not None and not isinstance(existing, VisorVTK):
            # TODO: update to check the VisorVtkLocal class type once VisorVTK has
            # been renamed VisorVtk with VisorVtkLocal as a concrete implementation/subclass.
            ignored.append(
                f"rendering_mode={rendering_mode} (existing instance type: {existing.__class__.__name__})"
            )
        if standalone is not None and existing.standalone != standalone:
            ignored.append(
                f"standalone={standalone} (existing value: {existing.standalone})"
            )
        if dark_mode is not None and existing.dark_mode != dark_mode:
            ignored.append(
                f"dark_mode={dark_mode} (existing value: {existing.dark_mode})"
            )
        if ignored:
            warnings = (
                f"Connected to existing Visor instance at {url}. "
                f"The following parameters were ignored because they cannot be "
                f"changed on an existing instance: {', '.join(ignored)}"
            )
            logger.warning(warnings)
            print(warnings)
        return warnings

    @classmethod
    def create_instance(
            cls,
            url: str,
            rendering_mode: RenderingMode,
            standalone: bool,
            dark_mode: bool,
            trame_log_dir: str | None = None
    ) -> None:
        """Create a new instance of Visor and store it in the cache."""
        cls._instances[url] = Visor(
            url=url,
            rendering_mode=rendering_mode,
            standalone=standalone,
            dark_mode=dark_mode,
            trame_log_dir=trame_log_dir,
        )
        msg = (
            f"Created new Visor instance for URL: {url} "
            f"(rendering_mode={rendering_mode}, standalone={standalone}, "
            f"dark_mode={dark_mode}, trame_log_dir={trame_log_dir})"
        )
        logger.info(msg)
        print(msg)

    @classmethod
    def delete_instance(cls, url: str) -> None:
        """Delete an instance of Visor from the cache."""
        if url not in cls._instances:
            return
        cls._instances.pop(url)
        return

    @classmethod
    def list_instances(cls) -> list[str]:
        """List URLs for all Visor instances in the cache."""
        return list(cls._instances.keys())
