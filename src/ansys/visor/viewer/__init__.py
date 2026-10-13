# Copyright 2026 ANSYS, Inc. All Rights Reserved.
# Restricted Rights Legend: See LICENSE for details.

from ansys.visor.viewer.core.metadata import Metadata

__all__ = ['Visor', 'Metadata']


def __getattr__(name):
    # Import Visor on first use so that lightweight subpackages (e.g. the CLI)
    # don't load the app and its module-level loggers, which open log files.
    if name == "Visor":
        from ansys.visor.viewer.app.visor import Visor
        return Visor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Version
# ------------------------------------------------------------------------------

try:
    import importlib.metadata as importlib_metadata  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import importlib_metadata  # type: ignore
__version__ = importlib_metadata.version("ansys-visor-viewer")

VERSION = __version__
