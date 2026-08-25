"""Networking utilities for Visor (port selection, admin-privilege detection)."""

import os
import socket


def is_user_admin() -> bool:
    """
    Check to see if the current user is likely to have root/administrator level system
    access. Under Windows, this is not a complete test, but it is a reasonable proxy.

    :returns bool: True if the current user has higher-level access permissions
    """
    try:
        # on Windows this will throw AttributeError
        return os.geteuid()
    except AttributeError:
        try:
            import ctypes

            # on non-Windows systems, this can be ModuleNotFoundError
            # on some Windows machines this can be AttributeError
            return ctypes.windll.shell32.IsUserAnAdmin() == 1
        except (ModuleNotFoundError, AttributeError):
            return False


def find_unused_port(
    host: str = "",
    avoid: list[int] | None = None,
) -> int | None:
    """
    Find a single unused port on the given host by asking the OS to allocate
    a free port from the ephemeral range.

    The probe binds on ``host`` (empty string ``""`` means all interfaces,
    equivalent to ``0.0.0.0``), so a port considered free here is free on
    the exact interface the caller intends to bind to.  This matters in
    multi-host / multi-interface setups where a port free on loopback may
    still be in use on an external interface.

    Non-admin users cannot bind to privileged ports [1-1023], so if such a
    port is somehow returned it is rejected.

    :param str host: hostname or IP to probe on (``""`` for all interfaces)
    :param Optional[List[int]] avoid: an optional list of ports not to return
    :returns Optional[int]: the detected port or None on failure
    """
    if avoid is None:
        avoid = []
    # Avoid handing back privileged ports to a non-privileged user
    is_admin = is_user_admin()
    # Try a bounded number of times in case the OS repeatedly hands us a
    # port that is in the "avoid" list or a privileged port.
    for _ in range(1000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, 0))
            port = sock.getsockname()[1]
        finally:
            sock.close()
        # skip privileged ports for non-admin users
        if not is_admin and port < 1024:
            continue
        if port in avoid:
            continue
        return port
    # in case we failed...
    return None
