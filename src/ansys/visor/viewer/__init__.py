# Copyright 2026 ANSYS, Inc. All Rights Reserved.
# Restricted Rights Legend: See LICENSE for details.

from ansys.visor.viewer.app.visor import Visor
from ansys.visor.viewer.core.metadata import Metadata

__all__ = ['Visor', 'Metadata']

# Version
# ------------------------------------------------------------------------------

try:
    import importlib.metadata as importlib_metadata  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import importlib_metadata  # type: ignore
__version__ = importlib_metadata.version("ansys-visor-viewer")

VERSION = __version__
