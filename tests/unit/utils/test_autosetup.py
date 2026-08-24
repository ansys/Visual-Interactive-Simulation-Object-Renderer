from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.utils.autosetup import prepare_wasm_assets

MODULE = "ansys.visor.viewer.utils.autosetup"


def _setup_common_mocks(monkeypatch, version="9.3"):
    """Set up shared mocks for metadata, regex, and trame server."""
    monkeypatch.setattr(f"{MODULE}.metadata.version", lambda _: version)
    monkeypatch.setattr(f"{MODULE}.re.findall", lambda pattern, text: [version])

    mock_server = MagicMock()
    monkeypatch.setattr(f"{MODULE}.trame_app.get_server", lambda: mock_server)

    return mock_server


def test_prepare_wasm_assets_linux_success(monkeypatch, tmp_path):
    """Verify successful WASM setup on Linux platform."""
    mock_server = _setup_common_mocks(monkeypatch)

    monkeypatch.setattr(f"{MODULE}.sys.platform", "linux")

    fake_site = tmp_path / "site-packages"
    wasm_src = fake_site / "trame_vtklocal/module/serve/wasm/9.3"
    wasm_src.mkdir(parents=True)

    monkeypatch.setattr(f"{MODULE}.site.getsitepackages", lambda: [str(fake_site)])

    copy_calls = {}

    def fake_copytree(src, dst):
        copy_calls["src"] = src
        copy_calls["dst"] = dst

    monkeypatch.setattr(f"{MODULE}.shutil.copytree", fake_copytree)
    monkeypatch.setattr(f"{MODULE}.shutil.rmtree", lambda path: None)

    prepare_wasm_assets(tmp_path)

    assert copy_calls["src"] == wasm_src
    assert "wasm" in str(copy_calls["dst"])
    mock_server.enable_module.assert_called_once()


def test_prepare_wasm_assets_windows_success(monkeypatch, tmp_path):
    """Verify successful WASM setup on Windows platform."""
    _setup_common_mocks(monkeypatch)

    monkeypatch.setattr(f"{MODULE}.sys.platform", "win32")

    wasm_src = tmp_path / ".venv/Lib/site-packages/trame_vtklocal/module/serve/wasm/9.3"
    wasm_src.mkdir(parents=True)

    monkeypatch.setattr(f"{MODULE}.shutil.copytree", lambda s, d: None)
    monkeypatch.setattr(f"{MODULE}.shutil.rmtree", lambda p: None)

    prepare_wasm_assets(tmp_path)


def test_prepare_wasm_assets_unsupported_platform(monkeypatch, tmp_path):
    """Ensure unsupported platforms raise RuntimeError."""
    _setup_common_mocks(monkeypatch)

    monkeypatch.setattr(f"{MODULE}.sys.platform", "darwin")

    with pytest.raises(RuntimeError):
        prepare_wasm_assets(tmp_path)


def test_prepare_wasm_assets_missing_wasm(monkeypatch, tmp_path):
    """Ensure missing WASM directory raises an exception."""
    _setup_common_mocks(monkeypatch)

    monkeypatch.setattr(f"{MODULE}.sys.platform", "linux")

    fake_site = tmp_path / "site-packages"
    fake_site.mkdir()

    monkeypatch.setattr(f"{MODULE}.site.getsitepackages", lambda: [str(fake_site)])

    with pytest.raises(Exception, match="WASM not found"):
        prepare_wasm_assets(tmp_path)


def test_main_calls_prepare(monkeypatch, tmp_path):
    """Ensure main() delegates to prepare_wasm_assets with cwd."""
    import ansys.visor.viewer.utils.autosetup as module

    called = {}

    def fake_prepare(path):
        called["path"] = path

    monkeypatch.setattr(module, "prepare_wasm_assets", fake_prepare)
    monkeypatch.setattr(module.Path, "cwd", lambda: tmp_path)

    module.main()

    assert called["path"] == tmp_path
