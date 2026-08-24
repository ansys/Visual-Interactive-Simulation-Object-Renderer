import pytest

from ansys.visor.viewer.core import visor_helpers


def test_get_random_javascript_safe_id_range_and_length():
    """Verify that generated JavaScript-safe IDs have the expected range and length."""
    for _ in range(10):
        val = visor_helpers.get_random_javascript_safe_id()
        assert 1000000000000000 <= val <= 9007199254740991
        assert len(str(val)) == 16

@pytest.mark.parametrize("url", [
    "http://localhost:8080",
    "http://127.0.0.1:5000",
    "http://example.com",
    "http://my-server.local",
])
def test_validate_url_valid(url):
    """Verify that valid URLs are accepted."""
    assert visor_helpers.validate_url(url) is not None

@pytest.mark.parametrize("url", [
    "ftp://example.com",
    "localhost:8080",
    "127.0.0.1",
    "example.com",
    "http:/bad.com",
    "",
    None,
])
def test_validate_url_invalid(url):
    """Verify that invalid URLs are rejected."""
    assert visor_helpers.validate_url(url) is None

@pytest.mark.parametrize("host", [
    "localhost",
    "127.0.0.1",
    "192.168.1.1",
    "example.com",
    "sub.domain.co.uk",
    "my-server.local",
])
def test_validate_host_valid(host):
    """Verify that valid host names are accepted."""
    assert visor_helpers.validate_host(host) is True

@pytest.mark.parametrize("host", [
    "http://localhost",
    "http://example.com",
    "localhost:8080",
    "127.0.0.1:5000",
    "bad host",
    "",
    None,
])
def test_validate_host_invalid(host):
    """Verify that invalid host names are rejected."""
    assert visor_helpers.validate_host(host) is False
