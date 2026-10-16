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
