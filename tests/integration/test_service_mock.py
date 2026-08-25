from os import path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from ansys.visor.viewer.api.server import app
from ansys.visor.viewer.core.metadata import Metadata

client = TestClient(app)
client_path = path.join(path.dirname(path.dirname(__file__)),'src','ansys','visor',"visor-client","dist")
input = path.join(path.dirname(__file__), "files","plate.vtp")
metadata = Metadata(name="test_model", unit="m")


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "http://localhost:8081" in response.json()['urls']

def test_info():
    """Test info API."""
    response = client.get("/info")
    assert response.status_code == 200
    assert response.json()['app_name'] == 'Visor Viewer'

def test_initialize():
    """Test initialize API."""
    response = client.post("/initialize",json={"host":"localhost","port":8081,"standalone":False})
    assert response.status_code == 200
    assert response.json()['message'] == 'Set active instance to http://localhost:8081'


@pytest.mark.anyio
async def test_start_endpoint_calls_start_async_with_args():
    """Test that start endpoint calls start async with args."""
    for route in app.routes:
        if route.path == "/start":
            visor_api_instance = route.endpoint.__self__
            break
    else:
        raise RuntimeError("Could not find VisorAPI instance for /start route")

    test_file_path = "some/test/file.vtu"
    test_timeout = 42
    with patch.object(
        visor_api_instance.visualizer, "_start_async", AsyncMock(return_value=("dataset_id", "task"))
    ) as mock_start_async:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/start", json={
                "file_path": test_file_path,
                "metadata": {"name": "model", "unit": "m"},
                "timeout": test_timeout
            })
        assert response.status_code in (200, 500)
        mock_start_async.assert_awaited_once_with(
            input=test_file_path, metadata=Metadata(name='model', unit='m'), timeout=test_timeout
        )

@pytest.mark.anyio
async def test_update_endpoint_calls_update_with_file_path():
    """Test that update endpoint calls update with file path."""
    for route in app.routes:
        if route.path == "/update":
            visor_api_instance = route.endpoint.__self__
            break
    else:
        raise RuntimeError("Could not find VisorAPI instance for /update route")

    test_file_path = "some/test/file.vtu"
    test_metadata = Metadata(name='model', unit='m')
    with patch.object(
            visor_api_instance.visualizer, "update", Mock(return_value=1)
    ) as mock_update:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/update", json={
                "file_path": test_file_path,
                "metadata": {"name": "model", "unit": "m"}
            })
        assert response.status_code in (200, 500)
        mock_update.assert_called_once_with(test_file_path, test_metadata)

@pytest.mark.anyio
async def test_stop_endpoint_calls_stop_instance():
    """Test that stop endpoint calls stop instance."""
    # Find the VisorAPI instance
    for route in app.routes:
        if route.path == "/stop_visualization":
            visor_api_instance = route.endpoint.__self__
            break
    else:
        raise RuntimeError("Could not find VisorAPI instance for /stop_visualization route")

    with patch.object(
        visor_api_instance.visualizer, "_stop_async", AsyncMock(return_value=None)
    ) as mock_stop_async:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/stop_visualization")
        assert response.status_code in (200, 500)
        mock_stop_async.assert_awaited_once()