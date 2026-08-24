"""Helper functions for Visor Viewer."""

import random
import re

from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet, vtkMultiPieceDataSet, vtkPolyData, vtkUnstructuredGrid

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)


def get_random_javascript_safe_id():
    """
    Returns a random integer between 1000000000000000 and 9007199254740991 (inclusive)
    that does not exceed JavaScript's Number.MAX_SAFE_INTEGER and is exactly 16 digits long.
    In JavaScript, double precision floating point format only has 52 bits to represent
    the mantissa, so it can only safely represent integers between -(253 – 1) and 253 – 1.
    This function is useful for cases where IDs need to be handed over to a JavaScript
    environment. Exceeding JavaScript's maximum integer will cause false positives
    when equating integers, for example, when searching an array of IDs in search of a
    specific ID.
    """
    return random.randint(1000000000000000, 9007199254740991)

def validate_url(url: str):
    """URL validation"""

    if url is None or not isinstance(url, str):
        return None

    regex = re.compile(
        r"^(?:http)?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return re.match(regex, url)

def validate_host(host: str) -> bool:
    """
    Validates a host string (domain, IP, or localhost) without protocol or port.
    Returns True if valid, False otherwise.
    """
    if host is None or not isinstance(host, str):
        return False

    regex = re.compile(
        r"^("  # start group
        r"(localhost)"  # localhost
        r"|"
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IPv4
        r"|"
        r"([A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9-]{1,63})+)"  # domain
        r")$", re.IGNORECASE
    )
    return re.match(regex, host) is not None

def is_composite_dataset(dataset) -> bool | None:
    """ Determine the node type based on the dataset type."""
    if isinstance(dataset, (vtkMultiBlockDataSet, vtkMultiPieceDataSet)):
        return True
    if isinstance(dataset, (vtkUnstructuredGrid, vtkPolyData)):
        return False
    msg = f"node type not yet supported: {type(dataset)}"
    logger.error(msg)
    raise RuntimeError(msg)
