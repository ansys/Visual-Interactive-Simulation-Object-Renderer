from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.api.visor_cache import VisorCache
from ansys.visor.viewer.app.paraview.paraview_handle import VisorParaviewHandle
from ansys.visor.viewer.core.pvserver_address import PvserverAddress
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
            rendering_mode=RenderingMode.CLIENT,
            standalone=False,
            dark_mode=False,
            pvserver=None,
            trame_log_dir="dir"
        )
        assert inst is mock_visor
        assert warnings is None
        assert "url1" in VisorCache._instances
        mock_cls.assert_called_once_with(
            url="url1",
            rendering_mode=RenderingMode.CLIENT,
            standalone=False,
            dark_mode=False,
            trame_log_dir="dir",
            pvserver=None,
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
            rendering_mode=RenderingMode.CLIENT,
            standalone=False,
            dark_mode=False,
            pvserver=None,
        )
        assert inst is mock_visor
        mock_cls.assert_not_called()


def test_create_instance_passes_pvserver():
    """The pvserver address reaches the Visor factory."""
    address = PvserverAddress(host="pv.example", port=22222)
    with patch("ansys.visor.viewer.api.visor_cache.Visor") as mock_cls:
        VisorCache.create_instance("url4", RenderingMode.PARAVIEW, True, False, address, "dir")

    mock_cls.assert_called_once_with(
        url="url4",
        rendering_mode=RenderingMode.PARAVIEW,
        standalone=True,
        dark_mode=False,
        trame_log_dir="dir",
        pvserver=address,
    )


def test_delete_instance_closes_instance():
    """A deleted instance is closed, so a PARAVIEW session process ends with it."""
    mock_visor = MagicMock()
    VisorCache._instances["url5"] = mock_visor

    VisorCache.delete_instance("url5")

    mock_visor.close.assert_called_once_with()


def make_handle(pvserver):
    handle = MagicMock(spec=VisorParaviewHandle)
    handle.standalone = True
    handle.dark_mode = False
    handle.pvserver = pvserver
    return handle


def test_existing_handle_accepted_without_warning():
    """A cached PARAVIEW handle asked for with its own arguments gives no warning."""
    address = PvserverAddress(host="pv.example", port=22222)
    VisorCache._instances["url6"] = make_handle(address)

    _inst, warnings = VisorCache.get_instance("url6", RenderingMode.PARAVIEW, True, False, address)

    assert warnings is None


def test_pvserver_mismatch_warns():
    """A different pvserver for a cached handle is ignored, with a warning naming both addresses."""
    VisorCache._instances["url7"] = make_handle(PvserverAddress(host="pv.example", port=22222))

    _inst, warnings = VisorCache.get_instance(
        "url7", RenderingMode.PARAVIEW, True, False, PvserverAddress(host="other", port=11111)
    )

    assert warnings == (
        "Connected to existing Visor instance at url7. "
        "The following parameters were ignored because they cannot be "
        "changed on an existing instance: pvserver=other:11111 (existing value: pv.example:22222)"
    )


def test_pvserver_for_non_handle_instance_warns():
    """A pvserver for a cached instance that is not a PARAVIEW handle is ignored, with a warning."""
    mock_visor = MagicMock()
    mock_visor.standalone = True
    mock_visor.dark_mode = False
    VisorCache._instances["url8"] = mock_visor

    _inst, warnings = VisorCache.get_instance(
        "url8", None, True, False, PvserverAddress(host="other", port=11111)
    )

    assert warnings == (
        "Connected to existing Visor instance at url8. "
        "The following parameters were ignored because they cannot be "
        "changed on an existing instance: pvserver=other:11111 (existing value: None)"
    )


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
