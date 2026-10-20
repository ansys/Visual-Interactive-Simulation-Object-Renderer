import pytest

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.part_properties import PartProperties
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_variable_record import VisorVariableRecord
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.persist.visor_ui_state import PersistedUIState
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState
from ansys.visor.viewer.models.runtime.scene.runtime_ui_state import RuntimeUIState
from ansys.visor.viewer.models.runtime.scene.runtime_view_state import RuntimeViewState
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


def _ui(dark_theme=False) -> RuntimeUIState:
    """A complete UI record from literals."""
    return RuntimeUIState(
        dark_theme=dark_theme,
        panel_top_left_panel_collapsed=False,
        panel_top_right_panel_collapsed=False,
        panel_top_right_legend_collapsed=False,
        panel_top_right_tab_index=0,
    )


def _camera(parallel_projection=False) -> VisorCameraState:
    """A camera record from literals."""
    return VisorCameraState(
        position=[1.0, 2.0, 3.0],
        focal_point=[4.0, 5.0, 6.0],
        view_up=[0.0, 0.0, 1.0],
        clipping_range=[7.0, 8.0],
        parallel_projection=parallel_projection,
        view_angle=30.0,
        parallel_scale=9.0,
    )


def _app_state(camera=None, **scene_fields) -> RuntimeAppState:
    """A runtime state with every scene-level field filled from literals unless given."""
    fields = {
        "unit": "m",
        "orthographic_enabled": None,
        "cross_section_enabled": False,
        "edges_enabled": False,
        "bounding_box_enabled": False,
    }
    fields.update(scene_fields)
    return RuntimeAppState(
        ui=_ui(),
        view=RuntimeViewState(camera=camera, cross_section=None),
        scene=RuntimeSceneState(**fields),
    )


def _mapper(registry=None) -> VisorStateMapper:
    return VisorStateMapper(registry or FakeRegistry(), _ui())


# ------------------------------------------------------------------
# Tests: init
# ------------------------------------------------------------------

def test_init_requires_registry():
    """Constructor should require dataset registry."""
    with pytest.raises(ValueError):
        VisorStateMapper(None, _ui())


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

    runtime_app_state = _app_state(camera=_camera(), edges_enabled=True)
    runtime_app_state.scene = runtime_app_state.scene.model_copy(update={
        "dataset_states": {1: "state-sentinel"},
        "variable_states": {"POINT::pressure::1": _literal_record()},
    })

    result = _mapper(registry).runtime_to_persisted(runtime_app_state)

    assert result == {"result": "ok"}
    assert called["datasets"] == {"dsA": {"converted": "state-sentinel"}}
    assert called["unit"] == "m"
    assert called["camera"] == _camera()
    assert called["edges_enabled"] is True
    assert called["ui_state"] == PersistedUIState(
        dark_theme=False,
        panel_top_left_panel_collapsed=False,
        panel_top_right_panel_collapsed=False,
        panel_top_right_legend_collapsed=False,
        panel_top_right_tab_index=0,
    )
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
    runtime_app_state = _app_state(variable_states={"POINT::pressure::1": _literal_record()})

    persisted = _mapper().runtime_to_persisted(runtime_app_state)

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

    captured = {}

    def fake_from_components(**kwargs):
        captured.update(kwargs)
        return "out"

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.PersistedViewerStateV1.from_components",
        fake_from_components,
    )

    runtime_app_state = _app_state()
    runtime_app_state.scene = runtime_app_state.scene.model_copy(update={"dataset_states": {123: "data"}})

    _mapper(FakeRegistry(datasets={})).runtime_to_persisted(runtime_app_state)

    assert captured["datasets"] == {}


# ------------------------------------------------------------------
# persisted_to_runtime
# ------------------------------------------------------------------

def _file(datasets=None) -> PersistedViewerStateV1:
    """A file whose scene names only its datasets."""
    return PersistedViewerStateV1.model_validate(
        {"scene": {"dataset_states": datasets or {}}}
    )


def test_persisted_to_runtime_basic():
    """persisted_to_runtime should convert dataset states via registry."""

    dataset = FakeDataset(name="dsA", did=10)
    registry = FakeRegistry(by_name={"dsA": dataset})
    entry = PartProperties(opacity=0.5)

    result = _mapper(registry).persisted_to_runtime(
        _file({"dsA": PersistedDatasetState(parts={"p": entry})}), _app_state()
    )

    assert result.scene.dataset_states == {10: {"rt": {"p": entry}}}


def test_persisted_to_runtime_missing_dataset_logs_warning(monkeypatch):
    """Missing dataset in registry should log warning and skip."""

    warnings = []

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_state_mapper.logger.warning",
        lambda msg: warnings.append(msg),
    )

    result = _mapper(FakeRegistry(by_name={})).persisted_to_runtime(
        _file({"missing": PersistedDatasetState()}), _app_state()
    )

    assert result.scene.dataset_states == {}
    assert len(warnings) == 1
    assert "not found in registry" in warnings[0]


def test_persisted_to_runtime_leaves_variable_states_empty():
    """The file's variable entries and the current records are both left out; the load path fills them."""

    current = _app_state(variable_states={"POINT::pressure::1": _literal_record()})
    state = PersistedViewerStateV1.model_validate({
        "scene": {
            "variable_states": {
                "POINT::pressure::1": {
                    "id": "POINT::pressure::1",
                    "arrayName": "pressure",
                    "type": "POINT",
                    "numComponents": 1,
                    "magnitudeRange": [1.0, 2.0],
                    "ranges": [[1.0, 2.0]],
                }
            }
        }
    })

    result = _mapper().persisted_to_runtime(state, current)

    assert result.scene.variable_states == {}


def test_persisted_to_runtime_does_not_write_back_to_dataset_state():
    """The mapper is not, and never has been, the registry-population path.

    It builds runtime dataset states and returns them; it never assigns them
    onto ``VisorDataset.state``.  That is the gap
    ``VisorSceneBase._restore_part_states`` closes, so the
    negative is pinned here rather than assumed.
    """

    dataset = FakeDataset(name="dsA", did=10)
    registry = FakeRegistry(by_name={"dsA": dataset})

    result = _mapper(registry).persisted_to_runtime(
        _file({"dsA": PersistedDatasetState()}), _app_state()
    )

    # The converted state is returned ...
    assert result.scene.dataset_states == {10: {"rt": {}}}
    # ... and is not written back onto the dataset the registry holds.
    assert dataset.state == "untouched-sentinel"

