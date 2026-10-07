import pytest

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.common.visor_variable_record import VisorVariableRecord
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.vtk.scene.visor_state_mapper import VisorStateMapper


def _literal_record() -> VisorVariableRecord:
    """A record whose custom range (2.0, 3.0) differs from its default (0.0, 10.0)."""
    return VisorVariableRecord(
        id="POINT::pressure::1",
        array_name="pressure",
        type=VisorVtkVariableType.POINT,
        num_components=1,
        part_ids=[1],
        default_magnitude_range=(0.0, 10.0),
        default_ranges=[(0.0, 10.0)],
        magnitude_range=(2.0, 3.0),
        ranges=[(2.0, 3.0)],
    )

# ------------------------------------------------------------------
# Helpers / fakes
# ------------------------------------------------------------------

class FakeDataset:
    """Fake dataset for testing."""
    def __init__(self, name, did):
        self.name = name
        self.id = did
        self.state = "untouched-sentinel"

    def runtime_to_persisted_state(self, state):
        return {"converted": state}

    def persisted_to_runtime_state(self, parts):
        return {"rt": parts}


class FakeRegistry:
    """ Fake dataset registry for testing."""
    def __init__(self, datasets=None, by_name=None):
        self.datasets = datasets or {}
        self._by_name = by_name or {}

    def get_by_name(self, name):
        return self._by_name.get(name)


# ------------------------------------------------------------------
# Tests: init
# ------------------------------------------------------------------

def test_init_requires_registry():
    """Constructor should require dataset registry."""
    with pytest.raises(ValueError):
        VisorStateMapper(None)


# ------------------------------------------------------------------
# runtime_to_persisted
# ------------------------------------------------------------------

def test_runtime_to_persisted_basic(monkeypatch):
    """runtime_to_persisted should convert datasets and pass through fields."""

    dataset = FakeDataset(name="dsA", did=1)
    registry = FakeRegistry(datasets={1: dataset})

    called = {}

    def fake_from_components(**kwargs):
        called.update(kwargs)
        return {"result": "ok"}

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.PersistedViewerStateV1.from_components",
        fake_from_components,
    )

    runtime_app_state = type("RuntimeAppState", (), {
        "ui": type("UI", (), {})(),
        "scene": type("Scene", (), {
            "unit": "m",
            "camera": "cam",
            "variable_states": {"POINT::pressure::1": _literal_record()},
            "dataset_states": {1: {"state": 123}},
            "cross_section": "cs",
            "orthographic_enabled": True,
            "cross_section_enabled": False,
            "edges_enabled": True,
            "bounding_box_enabled": False,
        })(),
    })()

    mapper = VisorStateMapper(registry)
    result = mapper.runtime_to_persisted(runtime_app_state)

    assert result == {"result": "ok"}
    assert called["datasets"] == {"dsA": {"converted": {"state": 123}}}
    assert called["unit"] == "m"
    assert called["camera"] == "cam"
    # The record is projected, not passed through.
    assert called["variable_states"] == {
        "POINT::pressure::1": VisorVariableState(
            id="POINT::pressure::1",
            array_name="pressure",
            type=VisorVtkVariableType.POINT,
            num_components=1,
            magnitude_range=(2.0, 3.0),
            ranges=[(2.0, 3.0)],
        )
    }


def test_runtime_to_persisted_projects_records_onto_the_persisted_entry():
    """#22: through the real persisted model, the saved entry carries the effective range and no default keys."""
    registry = FakeRegistry(datasets={})
    runtime_app_state = RuntimeAppState.from_components(
        ui=VisorUIState(),
        unit="m",
        dataset_states={},
        variable_states={"POINT::pressure::1": _literal_record()},
    )

    persisted = VisorStateMapper(registry).runtime_to_persisted(runtime_app_state)

    entry = persisted.model_dump(by_alias=True)["scene"]["variable_states"]["POINT::pressure::1"]
    assert entry == {
        "id": "POINT::pressure::1",
        "arrayName": "pressure",
        "type": "POINT",
        "numComponents": 1,
        "magnitudeRange": (2.0, 3.0),
        "ranges": [(2.0, 3.0)],
    }


def test_runtime_to_persisted_skips_missing_dataset(monkeypatch):
    """Datasets missing from registry should be skipped."""

    registry = FakeRegistry(datasets={})

    captured = {}

    def fake_from_components(**kwargs):
        captured.update(kwargs)
        return "out"

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.PersistedViewerStateV1.from_components",
        fake_from_components,
    )

    runtime_app_state = type("RuntimeAppState", (), {
        "ui": object(),
        "scene": type("Scene", (), {
            "unit": "m",
            "camera": "cam",
            "variable_states": {},
            "dataset_states": {123: {"data": 1}},
            "cross_section": None,
            "orthographic_enabled": False,
            "cross_section_enabled": False,
            "edges_enabled": False,
            "bounding_box_enabled": False,
        })(),
    })()

    mapper = VisorStateMapper(registry)
    mapper.runtime_to_persisted(runtime_app_state)

    assert captured["datasets"] == {}


# ------------------------------------------------------------------
# persisted_to_runtime
# ------------------------------------------------------------------

def test_persisted_to_runtime_basic(monkeypatch):
    """persisted_to_runtime should convert dataset states via registry."""

    dataset = FakeDataset(name="dsA", did=10)
    registry = FakeRegistry(by_name={"dsA": dataset})

    captured = {}

    def fake_from_components(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.RuntimeAppState.from_components",
        fake_from_components,
    )

    state = type("Persisted", (), {
        "ui": type("UI", (), {"dark_theme": True})(),
        "scene": type("Scene", (), {
            "unit": "mm",
            "camera": "cam",
            "variable_states": {"v": 1},
            "dataset_states": {
                "dsA": type("DS", (), {"parts": {"p": 9}})()
            },
            "cross_section": "cs",
            "orthographic_enabled": True,
            "cross_section_enabled": False,
            "edges_enabled": True,
            "bounding_box_enabled": False,
        })(),
    })()

    mapper = VisorStateMapper(registry)
    result = mapper.persisted_to_runtime(state)

    assert result == {"ok": True}
    assert captured["dataset_states"] == {10: {"rt": {"p": 9}}}
    assert captured["unit"] == "mm"
    assert captured["camera"] == "cam"


def test_persisted_to_runtime_missing_dataset_logs_warning(monkeypatch):
    """Missing dataset in registry should log warning and skip."""

    registry = FakeRegistry(by_name={})

    warnings = []

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.logger.warning",
        lambda msg: warnings.append(msg),
    )

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.RuntimeAppState.from_components",
        lambda **kwargs: kwargs,
    )

    state = type("Persisted", (), {
        "ui": type("UI", (), {"dark_theme": False})(),
        "scene": type("Scene", (), {
            "unit": None,
            "camera": None,
            "variable_states": {},
            "dataset_states": {
                "missing": type("DS", (), {"parts": {}})()
            },
            "cross_section": None,
            "orthographic_enabled": False,
            "cross_section_enabled": False,
            "edges_enabled": False,
            "bounding_box_enabled": False,
        })(),
    })()

    mapper = VisorStateMapper(registry)
    result = mapper.persisted_to_runtime(state)

    assert result["dataset_states"] == {}
    assert len(warnings) == 1
    assert "not found in registry" in warnings[0]


def test_persisted_to_runtime_handles_none_variable_states(monkeypatch):
    """None variable_states should default to empty dict."""

    dataset = FakeDataset(name="dsA", did=1)
    registry = FakeRegistry(by_name={"dsA": dataset})

    captured = {}

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.RuntimeAppState.from_components",
        lambda **kwargs: captured.update(kwargs) or kwargs,
    )

    state = type("Persisted", (), {
        "ui": type("UI", (), {"dark_theme": False})(),
        "scene": type("Scene", (), {
            "unit": "m",
            "camera": "cam",
            "variable_states": None,
            "dataset_states": {},
            "cross_section": None,
            "orthographic_enabled": False,
            "cross_section_enabled": False,
            "edges_enabled": False,
            "bounding_box_enabled": False,
        })(),
    })()

    mapper = VisorStateMapper(registry)
    mapper.persisted_to_runtime(state)

    assert captured["variable_states"] == {}


def test_persisted_to_runtime_does_not_write_back_to_dataset_state(monkeypatch):
    """The mapper is not, and never has been, the registry-population path.

    It builds runtime dataset states and returns them; it never assigns them
    onto ``VisorDataset.state``.  That is the gap
    ``VisorSceneBase._restore_part_states`` closes, so the
    negative is pinned here rather than assumed.
    """

    dataset = FakeDataset(name="dsA", did=10)
    registry = FakeRegistry(by_name={"dsA": dataset})

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.RuntimeAppState.from_components",
        lambda **kwargs: kwargs,
    )

    state = type("Persisted", (), {
        "ui": type("UI", (), {"dark_theme": False})(),
        "scene": type("Scene", (), {
            "unit": "m",
            "camera": None,
            "variable_states": {},
            "dataset_states": {
                "dsA": type("DS", (), {"parts": {"p": 9}})()
            },
            "cross_section": None,
            "orthographic_enabled": False,
            "cross_section_enabled": False,
            "edges_enabled": False,
            "bounding_box_enabled": False,
        })(),
    })()

    mapper = VisorStateMapper(registry)
    result = mapper.persisted_to_runtime(state)

    # The converted state is returned ...
    assert result["dataset_states"] == {10: {"rt": {"p": 9}}}
    # ... and is not written back onto the dataset the registry holds.
    assert dataset.state == "untouched-sentinel"

