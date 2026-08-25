from unittest.mock import patch

import ansys.visor.viewer.config as config


def test_settings_defaults():
    """Verify that settings defaults work."""
    s = config.Settings()
    assert s.app_name == "Visor Viewer"
    assert s.default_host == "localhost"
    assert s.default_port == 8081
    assert s.default_standalone is True
    assert "client_bundle" in s.default_client_bundle
    assert "logs" in s.default_log_dir
    assert s.trame_log_dir is None

def test_get_client_bundle_standalone_true():
    """Verify that getting the client bundle works when standalone is True."""
    s = config.Settings()
    result = s.get_client_bundle(standalone=True)
    assert result == s.default_client_bundle

def test_get_client_bundle_standalone_false():
    """Verify that getting client bundle is None when standalone is False."""
    s = config.Settings()
    result = s.get_client_bundle(standalone=False)
    assert result is None

def test_settings_customise_sources_file_exists(tmp_path, monkeypatch):
    """Verify that .visor custom settings are loaded and certain keys are removed."""
    # Create a fake .visor file in a temporary directory
    config_file = tmp_path / ".visor"
    config_file.write_text("irrelevant")

    # Patch cwd so Settings looks in our tmp directory
    monkeypatch.chdir(tmp_path)

    # Fake YAML content returned by yaml.safe_load
    fake_yaml = {
        "app_name": "ShouldBeRemoved",
        "default_client_bundle": "ShouldBeRemoved",
        "default_host": "customhost",
    }

    with patch("yaml.safe_load", return_value=fake_yaml):
        sources = config.Settings.settings_customise_sources(
            None, "init", "env", "file", foo="bar"
        )
        file_settings_func = sources[0]
        result = file_settings_func()

    # Assertions
    assert "app_name" not in result
    assert "default_client_bundle" not in result
    assert result["default_host"] == "customhost"

def test_settings_customise_sources_file_not_exists(tmp_path, monkeypatch):
    """Verify that .visor custom settings are not loaded when the file does not exist."""
    monkeypatch.chdir(tmp_path)
    sources = config.Settings.settings_customise_sources(None, "init", "env", "file", foo="bar")
    file_settings_func = sources[0]
    result = file_settings_func()
    assert result == {}


def test_settings_instance_exists():
    """Verify that the global settings object is an instance of Settings"""
    assert isinstance(config.settings, config.Settings)
