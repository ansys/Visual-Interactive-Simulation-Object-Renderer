import pytest

from ansys.visor.viewer.app.visor import Visor


class ConcreteVisor(Visor):
    def start(self, input=None, metadata=None, timeout=0, on_server_started=None):
        self.started = True

    def stop(self):
        self.stopped = True

    def update(self, input, metadata=None):
        self.updated = True

    def save_state(self, state_dir):
        self.state_saved = state_dir

    def load_state(self, state_dir):
        self.state_loaded = state_dir

    def _health(self):
        return True

    async def _start_async(self, input=None, metadata=None, timeout=0):
        self.async_started = True

    async def _stop_async(self):
        self.async_stopped = True

    def add_dataset(self, input, metadata=None):
        self.dataset_added = True

    def remove_dataset(self, dataset_id):
        self.dataset_removed = dataset_id

    def list_datasets(self):
        return {
            1: {
                "id": 1,
                "name": "foo",
                "unit": "m",
                "file_path": None,
                "metadata_path": None,
            }
        }

def test_factory_returns_subclass():
    """Verify that the Visor factory returns a concrete implementation."""
    obj = Visor(url="http://localhost:1234")
    from ansys.visor.viewer.app.visor_vtk import VisorVTK
    assert isinstance(obj, VisorVTK)

def test_invalid_rendering_engine_raises():
    """Verify that an invalid rendering engine raises a ValueError."""
    class DummyEngine:
        pass
    with pytest.raises(ValueError):
        Visor(rendering_engine=DummyEngine)

def test_set_default_url_sets_properties(monkeypatch):
    """Verify that default settings are used to construct the URL."""
    monkeypatch.setattr("ansys.visor.viewer.config.settings.default_host", "localhost")
    monkeypatch.setattr("ansys.visor.viewer.config.settings.default_port", 1234)
    monkeypatch.setattr("ansys.visor.viewer.config.settings.app_name", "TestApp")
    obj = ConcreteVisor()
    assert obj.host == "localhost"
    assert obj.port == 1234
    assert obj.url == "http://localhost:1234"

def test_set_url_sets_properties():
    """Verify that host, port, and URL are parsed from the provided URL."""
    obj = ConcreteVisor(url="http://127.0.0.1:8080")
    assert obj.host == "127.0.0.1"
    assert obj.port == 8080
    assert obj.url == "http://127.0.0.1:8080"

def test_info_returns_expected_dict(monkeypatch):
    """Verify that info returns the expected viewer metadata."""
    monkeypatch.setattr("ansys.visor.viewer.config.settings.app_name", "TestApp")
    obj = ConcreteVisor()
    info = obj.info()
    assert info["app_name"] == "TestApp"
    assert info["host"] == obj.host
    assert info["port"] == obj.port
    assert info["standalone"] == obj.standalone
    assert info["datasets"] == ["foo"]

def test_standalone_property():
    """Verify that the standalone property reflects the configured value."""
    obj = ConcreteVisor(standalone=False)
    assert obj.standalone is False

def test_abstract_methods_raise():
    """Verify that unimplemented abstract methods raise NotImplementedError."""
    class DummyVisor(Visor):
        @property
        def datasets(self):
            raise NotImplementedError()

        def start(self, *a, **kw):
            raise NotImplementedError()

        def stop(self):
            raise NotImplementedError()

        def update(self, *a, **kw):
            raise NotImplementedError()

        def save_state(self, state_dir):
            raise NotImplementedError()

        def load_state(self, state_dir):
            raise NotImplementedError()

        def _health(self):
            raise NotImplementedError()

        async def _start_async(self, *a, **kw):
            raise NotImplementedError()

        async def _stop_async(self):
            raise NotImplementedError()

        def add_dataset(self, *a, **kw):
            raise NotImplementedError()

        def remove_dataset(self, dataset_id):
            raise NotImplementedError()

        def list_datasets(self):
            raise NotImplementedError()

    dummy = DummyVisor()
    with pytest.raises(NotImplementedError):
        _ = dummy.datasets
    with pytest.raises(NotImplementedError):
        dummy.start()
    with pytest.raises(NotImplementedError):
        dummy.stop()
    with pytest.raises(NotImplementedError):
        dummy.update("input")
    with pytest.raises(NotImplementedError):
        dummy.save_state("dir")
    with pytest.raises(NotImplementedError):
        dummy.load_state("dir")
    with pytest.raises(NotImplementedError):
        dummy._health()
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(dummy._start_async())
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(dummy._stop_async())
    with pytest.raises(NotImplementedError):
        dummy.add_dataset("input")
    with pytest.raises(NotImplementedError):
        dummy.remove_dataset(1)
    with pytest.raises(NotImplementedError):
        dummy.list_datasets()

def test_concrete_methods_work():
    """Verify that the concrete implementation methods update state as expected."""
    obj = ConcreteVisor()
    obj.start()
    assert obj.started
    obj.stop()
    assert obj.stopped
    obj.update("input")
    assert obj.updated
    obj.save_state("dir")
    assert obj.state_saved == "dir"
    obj.load_state("dir")
    assert obj.state_loaded == "dir"
    assert obj._health() is True
    import asyncio
    asyncio.run(obj._start_async())
    assert obj.async_started
    asyncio.run(obj._stop_async())
    assert obj.async_stopped
    obj.add_dataset("input")
    assert obj.dataset_added
    obj.remove_dataset(42)
    assert obj.dataset_removed == 42
    assert list(obj.list_datasets().keys()) == [1]
