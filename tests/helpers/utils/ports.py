# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Iterator, Tuple


def _exclusive_sock() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Prefer exclusive use on Windows to avoid TIME_WAIT and reuse pitfalls
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    # Do NOT set SO_REUSEADDR for a guard/probe since apparently it can mask conflicts on Unix.
    return s

def reserve_free_port(host: str = "127.0.0.1") -> Tuple[str, int, socket.socket]:
    """
    Bind a guard socket to an ephemeral port chosen by the OS and return (host, port, guard_socket).
    - Keep the guard socket bound to the port until the server is ready to request its use.
    """
    s = _exclusive_sock()
    # Ask OS for a free ephemeral port
    s.bind((host, 0))
    # Listen so the port is truly reserved for TCP
    s.listen(1)
    addr, port = s.getsockname()

    return host, port, s

@contextmanager
def reserved_port(host: str = "127.0.0.1") -> Iterator[Tuple[str, int, socket.socket]]:
    """
    Context manager that reserves a free port and yields (host, port, guard_socket).
    guard_socket must stay open until the server is listening, then close it.
    """
    h, p, guard = reserve_free_port(host)
    try:
        yield h, p, guard
    finally:
        try:
            guard.close()
        except Exception:
             pass

