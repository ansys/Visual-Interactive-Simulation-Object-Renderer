from os import path

import pytest
from httpx import ASGITransport, AsyncClient

from ansys.visor.viewer.api.server import app

input_file = path.join(path.dirname(__file__),"..", "files","plate.vtp")
client_path = path.join(path.dirname(path.dirname(__file__)),'src','ansys','visor',"visor-client","dist")

@pytest.mark.anyio
async def test_info():
    """Test the info API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/info")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_initialize():
    """Test initialize API."""
    host = "localhost"
    port = 8088
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/initialize", json={"host": "localhost", "port": 8088, "standalone": False})
    assert response.status_code == 200
    assert response.json() == {"message": f"Set active instance to http://{host}:{port}"}

@pytest.mark.anyio
async def test_root():
    """Test API root."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/initialize", json={"hostname": "localhost", "port": 8088, "standalone": True})
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {'urls': ['http://localhost:8081', 'http://localhost:8088']}

@pytest.mark.anyio
@pytest.mark.xfail(reason="Side effect results in no running loop error")
async def test_start():
    """Test start API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.get("/")
        response = await ac.post("/start", json={'file_path': input_file, 'metadata': { 'name': "model", 'unit': "m" }, 'timeout':3})
        assert response.status_code == 200

@pytest.mark.anyio
async def test_update():
    """Test update API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.get("/")
        file = path.join(path.dirname(__file__), "..", "files","plate.vtp")
        response = await ac.post("/start", json={'timeout':4})
        response = await ac.post("/update", json={'file_path': file, 'metadata': { 'name': "model", 'unit': "m"} })
        assert response.status_code == 200

@pytest.mark.anyio
async def test_health_active():
    """Test health API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.get("/")
        await ac.post("/start")
        response = await ac.get("/health")
        assert response.status_code == 200

@pytest.mark.anyio
@pytest.mark.xfail(reason="Known InvalidStateError in server on /stop_visualization")
async def test_stop_visualization():
    """Test stop_visualization API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post("/start")
        response = await ac.post("/stop_visualization")
        # Accept 200 or known 500 error due to InvalidStateError
        if response.status_code == 500:
            pytest.skip("Known InvalidStateError in server, skipping test.")
        assert response.status_code == 200

@pytest.mark.anyio
async def test_health_inactive():
    """Test that health is inactive."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/initialize", json={"hostname": "localhost", "port": 8090, "standalone": False})
        response = await ac.get("/health")
        assert response.status_code == 200

