import asyncio

import pytest

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


# ------------------------------------------------------------------
# request_state
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_state_resolves(monkeypatch):
    """request_state should await and return resolved response."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.get_random_javascript_safe_id",
        lambda: 10,
    )

    class FakeRequest:
        def __init__(self, request_id): # noqa: N803
            self.request_id = request_id

        def model_dump(self, exclude_none=True, by_alias=True):
            return {"requestId": self.request_id}

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateRequest",
        FakeRequest,
    )

    # ✅ FIX: mock model_validate
    class FakeResponse:
        def __init__(self, request_id): # noqa: N803
            self.request_id = request_id

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateResponse.model_validate",
        lambda data: FakeResponse(data["requestId"]),
    )

    server = FakeServer()
    bridge = VisorFrontendBridge(server, "visor-frontend-ref")

    async def resolve_later():
        await asyncio.sleep(0)
        bridge.resolve_save_state_response(10, {"requestId": 10})

    asyncio.create_task(resolve_later())

    response = await bridge.request_state(timeout=1)

    assert response.request_id == 10
    assert len(server.calls) == 1
    assert bridge._ref_name == "visor-frontend-ref"
    assert server.calls[0][0] == "visor-frontend-ref"
    assert server.calls[0][1] == "getState"


@pytest.mark.asyncio
async def test_request_state_cleans_up(monkeypatch):
    """Pending request should be removed after completion."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.get_random_javascript_safe_id",
        lambda: 1,
    )

    class FakeRequest:
        def __init__(self, request_id): # noqa: N803
            self.request_id = request_id

        def model_dump(self, exclude_none=True, by_alias=True):
            return {"requestId": self.request_id}

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateRequest",
        FakeRequest,
    )

    # ✅ FIX: mock model_validate
    class FakeResponse:
        def __init__(self, request_id): # noqa: N803
            self.request_id = request_id

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateResponse.model_validate",
        lambda data: FakeResponse(data["requestId"]),
    )

    server = FakeServer()
    bridge = VisorFrontendBridge(server, "visor-frontend-ref")

    async def resolve():
        await asyncio.sleep(0)
        bridge.resolve_save_state_response(1, {"requestId": 1})

    asyncio.create_task(resolve())
    await bridge.request_state(timeout=1)

    assert bridge._pending_requests == {}
    assert bridge._pending_loop is None


# ------------------------------------------------------------------
# resolve_save_state_response
# ------------------------------------------------------------------

def test_resolve_sets_result(monkeypatch):
    """resolve_save_state_response should complete pending future."""

    class FakeResponse:
        def __init__(self, request_id): # noqa: N803
            self.request_id = request_id

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateResponse.model_validate",
        lambda data: FakeResponse(data["requestId"]),
    )

    bridge = VisorFrontendBridge(FakeServer(), "visor-frontend-ref")

    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    bridge._pending_requests[5] = fut
    bridge._pending_loop = None

    bridge.resolve_save_state_response(5, {"requestId": 5})

    assert fut.done()
    assert fut.result().request_id == 5


def test_resolve_invalid_response_sets_exception(monkeypatch):
    """Invalid response should set exception on future."""

    from pydantic import ValidationError

    def raise_error(_):
        raise ValidationError.from_exception_data("x", [])

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateResponse.model_validate",
        raise_error,
    )

    bridge = VisorFrontendBridge(FakeServer(), "visor-frontend-ref")

    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    bridge._pending_requests[1] = fut
    bridge._pending_loop = None

    with pytest.raises(ValueError):
        bridge.resolve_save_state_response(1, {})

    assert fut.done()
    assert isinstance(fut.exception(), ValidationError)


def test_resolve_unknown_request_logs_warning(monkeypatch):
    """Unknown request_id should trigger warning."""

    warnings = []

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.logger.warning",
        lambda msg: warnings.append(msg),
    )

    class FakeResponse:
        def __init__(self, request_id): # noqa: N803
            self.request_id = request_id

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateResponse.model_validate",
        lambda data: FakeResponse(data["requestId"]),
    )

    bridge = VisorFrontendBridge(FakeServer(), "visor-frontend-ref")

    bridge.resolve_save_state_response(999, {"requestId": 999})

    assert len(warnings) == 1
    assert "no pending async waiter" in warnings[0]


# ------------------------------------------------------------------
# threadsafe helpers
# ------------------------------------------------------------------

def test_threadsafe_set_result_no_loop():
    """_threadsafe_set_result should set result without loop."""

    bridge = VisorFrontendBridge(None, "")

    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    bridge._threadsafe_set_result(None, fut, "value")

    assert fut.done()
    assert fut.result() == "value"


def test_threadsafe_set_exception_no_loop():
    """_threadsafe_set_exception should set exception without loop."""

    bridge = VisorFrontendBridge(None, "")

    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    exc = RuntimeError("error")
    bridge._threadsafe_set_exception(None, fut, exc)

    assert fut.done()
    assert fut.exception() is exc


def test_threadsafe_helpers_ignore_done_future():
    """Threadsafe helpers should not overwrite completed futures."""

    bridge = VisorFrontendBridge(None, "")

    loop = asyncio.new_event_loop()
    fut = loop.create_future()
    fut.set_result("done")

    bridge._threadsafe_set_result(None, fut, "new")
    bridge._threadsafe_set_exception(None, fut, RuntimeError())

    assert fut.result() == "done"

def test_resolve_unexpected_exception_sets_exception_and_reraises(monkeypatch):
    """Unexpected exception during validation should set future exception and re-raise."""

    # Force a non-ValidationError exception
    def raise_unexpected(_):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorSaveStateResponse.model_validate",
        raise_unexpected,
    )

    bridge = VisorFrontendBridge(FakeServer(), "visor-frontend-ref")

    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    bridge._pending_requests[42] = fut
    bridge._pending_loop = None

    with pytest.raises(RuntimeError):
        bridge.resolve_save_state_response(42, {"requestId": 42})

    # Future should be completed with the same exception
    assert fut.done()
    assert isinstance(fut.exception(), RuntimeError)
    assert str(fut.exception()) == "boom"
