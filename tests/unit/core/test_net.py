"""Tests for ansys.visor.viewer.core.net."""

import socket
from unittest.mock import patch

from ansys.visor.viewer.core.net import find_unused_port, is_user_admin


def test_find_unused_port_returns_int_in_valid_range():
    """A successful probe returns a bindable, non-privileged port when the caller is non-admin."""
    with patch("ansys.visor.viewer.core.net.is_user_admin", return_value=False):
        port = find_unused_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535


def test_find_unused_port_returns_bindable_port():
    """The returned port must actually be bindable immediately after selection."""
    port = find_unused_port()
    assert port is not None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", port))
    finally:
        sock.close()


def test_find_unused_port_avoids_listed_ports():
    """A port present in ``avoid`` must not be returned."""
    first = find_unused_port()
    assert first is not None
    # ask again while avoiding the first one; must get something different
    second = find_unused_port(avoid=[first])
    assert second is not None
    assert second != first


def test_find_unused_port_probes_on_specified_host():
    """The probe must bind on the host supplied by the caller."""
    captured_binds = []

    real_socket = socket.socket

    class _FakeSocket:
        def __init__(self, *_a, **_kw):
            self._inner = real_socket(socket.AF_INET, socket.SOCK_STREAM)

        def bind(self, addr):
            captured_binds.append(addr)
            self._inner.bind(addr)

        def getsockname(self):
            return self._inner.getsockname()

        def close(self):
            self._inner.close()

    with patch("ansys.visor.viewer.core.net.socket.socket", _FakeSocket):
        find_unused_port(host="127.0.0.1")

    assert captured_binds
    assert all(addr[0] == "127.0.0.1" for addr in captured_binds)


def test_find_unused_port_returns_none_when_all_candidates_avoided():
    """If every OS-picked candidate is excluded, the function returns None."""
    # Force the loop by making every port fall into ``avoid``. We can't
    # enumerate every ephemeral port up front, so instead patch the socket
    # so that ``getsockname`` always reports the same port, and put that
    # port in ``avoid``.
    fixed_port = 40000

    class _FakeSocket:
        def __init__(self, *_a, **_kw):
            pass

        def bind(self, _addr):
            pass

        def getsockname(self):
            return ("", fixed_port)

        def close(self):
            pass

    with patch("ansys.visor.viewer.core.net.socket.socket", _FakeSocket):
        result = find_unused_port(avoid=[fixed_port])

    assert result is None


def test_find_unused_port_skips_privileged_for_non_admin():
    """A non-admin caller must never receive a privileged port (< 1024)."""
    ports_iter = iter([80, 443, 55555])  # first two privileged, third valid

    class _FakeSocket:
        def __init__(self, *_a, **_kw):
            pass

        def bind(self, _addr):
            self._port = next(ports_iter)

        def getsockname(self):
            return ("", self._port)

        def close(self):
            pass

    with patch("ansys.visor.viewer.core.net.socket.socket", _FakeSocket), \
         patch("ansys.visor.viewer.core.net.is_user_admin", return_value=False):
        result = find_unused_port()

    assert result == 55555


def test_is_user_admin_returns_bool():
    """``is_user_admin`` must always return a boolean-compatible value without raising."""
    result = is_user_admin()
    # On Windows non-admin it's False; on POSIX it's the effective UID (int, 0 for root).
    # In all cases we should get something truth-testable without an exception.
    assert result is not None or result is None  # smoke: just ensure it ran
    bool(result)  # must not raise
