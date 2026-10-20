from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState
from ansys.visor.viewer.models.runtime.scene.runtime_ui_state import RuntimeUIState
from ansys.visor.viewer.models.runtime.scene.runtime_view_state import RuntimeViewState
from ansys.visor.viewer.vtk.scene.visor_frontend_bridge import VisorFrontendBridge

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

class FakeServer:
    """ A fake server that records JS calls made to it."""
    def __init__(self):
        self.calls = []

    def js_call(self, ref, method, payload):
        self.calls.append((ref, method, payload))



# ------------------------------------------------------------------
# set_state
# ------------------------------------------------------------------

def test_set_state_sends_js_call(monkeypatch):
    """set_state should send a JS call with serialized request."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.get_random_javascript_safe_id",
        lambda: 123,
    )

    class FakeRequest:
        def __init__(self, request_id, app_state): # noqa: N803
            self.request_id = request_id
            self.app_state = app_state

        def model_dump(self, by_alias=True):
            return {"id": self.request_id}

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorLoadStateRequest",
        FakeRequest,
    )

    server = FakeServer()

    bridge = VisorFrontendBridge(server, "visor-frontend-ref")
    result = bridge.set_state("state")

    assert result == 123
    assert bridge._ref_name == "visor-frontend-ref"
    assert server.calls[0][0] == "visor-frontend-ref"
    assert server.calls[0][1] == "setState"
    assert server.calls[0][2] == {"id": 123}


def test_load_push_carries_camera_and_plane_under_the_view():
    """The real request, dumped by the real bridge call: camera and plane sit in appState.view, not the scene."""
    state = RuntimeAppState(
        ui=RuntimeUIState(
            dark_theme=True,
            panel_top_left_panel_collapsed=False,
            panel_top_right_panel_collapsed=False,
            panel_top_right_legend_collapsed=False,
            panel_top_right_tab_index=0,
        ),
        view=RuntimeViewState(
            camera=VisorCameraState(
                position=[1.0, 2.0, 3.0],
                focal_point=[4.0, 5.0, 6.0],
                view_up=[0.0, 0.0, 1.0],
                clipping_range=[7.0, 8.0],
                parallel_projection=True,
                view_angle=30.0,
                parallel_scale=9.0,
            ),
            cross_section=VisorCrossSectionState(origin=[0.5, 0.5, 0.5], normal=[0.0, 1.0, 0.0]),
        ),
        scene=RuntimeSceneState(
            unit="mm",
            orthographic_enabled=True,
            cross_section_enabled=False,
            edges_enabled=True,
            bounding_box_enabled=False,
        ),
    )
    server = FakeServer()

    VisorFrontendBridge(server, "visor-frontend-ref").set_state(state)

    app_state = server.calls[0][2]["appState"]
    assert "camera" not in app_state["scene"]
    assert "crossSection" not in app_state["scene"]
    assert app_state["view"]["camera"] == {
        "position": [1.0, 2.0, 3.0],
        "focalPoint": [4.0, 5.0, 6.0],
        "viewUp": [0.0, 0.0, 1.0],
        "clippingRange": [7.0, 8.0],
        "parallelProjection": True,
        "viewAngle": 30.0,
        "parallelScale": 9.0,
    }
    assert app_state["view"]["crossSection"] == {"origin": [0.5, 0.5, 0.5], "normal": [0.0, 1.0, 0.0]}
