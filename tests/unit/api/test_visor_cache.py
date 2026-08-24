from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.api.visor_cache import VisorCache
from ansys.visor.viewer.core.visor_enums import RenderingMode


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the instance cache before each test."""
    # Ensure cache is empty before each test
    VisorCache._instances.clear()


def test_get_instance_creates_new(monkeypatch):
    """Verify that a new instance is created when none exists."""
    mock_visor = MagicMock()
    with patch("ansys.visor.viewer.api.visor_cache.Visor", return_value=mock_visor) as mock_cls:
        inst, warnings = VisorCache.get_instance(
            "url1",
            rendering_mode=RenderingMode.LOCAL,
            standalone=False,
            dark_mode=False,
            trame_log_dir="dir"
        )
        assert inst is mock_visor
        assert warnings is None
        assert "url1" in VisorCache._instances
        mock_cls.assert_called_once_with(
            url="url1",
            rendering_mode=RenderingMode.LOCAL,
            standalone=False,
            dark_mode=False,
            trame_log_dir="dir"
        )


def test_get_instance_returns_existing(monkeypatch):
    """Verify that an existing instance is returned from the cache."""
    mock_visor = MagicMock()
    mock_visor.standalone = False
    mock_visor.dark_mode = False
    VisorCache._instances["url2"] = mock_visor

    with patch("ansys.visor.viewer.api.visor_cache.Visor") as mock_cls:
        inst, warnings = VisorCache.get_instance(
            "url2",
            rendering_mode=RenderingMode.LOCAL,
            standalone=False,
            dark_mode=False
        )
        assert inst is mock_visor
        mock_cls.assert_not_called()


def test_delete_instance_removes(monkeypatch):
    """Verify that an instance is removed from the cache."""
    mock_visor = MagicMock()
    VisorCache._instances["url3"] = mock_visor

    VisorCache.delete_instance("url3")

    assert "url3" not in VisorCache._instances


def test_delete_instance_noop_if_missing(monkeypatch):
    """Verify that deleting a missing instance has no effect."""
    # Should not raise or change anything
    VisorCache.delete_instance("missing_url")
    assert VisorCache._instances == {}


def test_list_instances_returns_keys(monkeypatch):
    """Verify that cached instance URLs are returned."""
    VisorCache._instances["urlA"] = MagicMock()
    VisorCache._instances["urlB"] = MagicMock()

    urls = VisorCache.list_instances()

    assert set(urls) == {"urlA", "urlB"}
