import os
from typing import Coroutine

import pytest

from ansys.visor.viewer import Visor

input_file = os.path.join(os.path.dirname(__file__), "..", "files", "plate.vtp")

def test_start_stop():
    """Test start and stop."""
    vis = Visor(url="http://localhost:8081")
    vis.start(input=input_file)
    assert vis.running is True
    vis.stop()
    assert vis.running is False


@pytest.mark.asyncio
async def test_start_async_stop_async():
    """Test start_async and stop_async."""
    vis = Visor(url="http://localhost:8081")
    dataset_id, coro = await vis._start_async(input=input_file)
    assert vis.running is True
    assert isinstance(coro, Coroutine)
    await vis._stop_async()
    assert vis.running is False


@pytest.mark.asyncio
async def test_start_async_stop():
    """Test start_async and stop."""
    vis = Visor(url="http://localhost:8081")
    dataset_id, coro = await vis._start_async(input=input_file)
    assert vis.running is True
    assert isinstance(coro, Coroutine)
    vis.stop()
    assert vis.running is False


@pytest.mark.asyncio
async def test_start_stop_async():
    """Test start and stop_async."""
    vis = Visor(url="http://localhost:8081")
    vis.start(input=input_file)
    assert vis.running is True
    await vis._stop_async()
    assert vis.running is False


def test_double_start():
    """Test double start."""
    vis = Visor(url="http://localhost:8081")
    vis.start(input=input_file)
    with pytest.raises(BaseException):
        vis.start(input=input_file)
    vis.stop()


@pytest.mark.asyncio
async def test_double_start_async():
    """Test double start_async."""
    vis = Visor(url="http://localhost:8081")
    await vis._start_async(input=input_file)
    with pytest.raises(BaseException):
        await vis._start_async(input=input_file)
    vis.stop()


def test_update():
    """Test update after start."""
    vis = Visor(url="http://localhost:8081")
    vis.start(input=input_file)
    vis.update(input=input_file)
    vis.stop()


@pytest.mark.asyncio
async def test_update_async():
    """Test that update after start_async."""
    vis = Visor(url="http://localhost:8081")
    await vis._start_async(input=input_file)
    vis.update(input=input_file)
    await vis._stop_async()

# async def main():
#     test_start_stop()
#     await test_start_async_stop_async()
#     await test_start_async_stop()
#     await test_start_stop_async()
#     test_double_start()
#     await test_double_start_async()
#     await test_update_async()
#
#
# asyncio.run(main())
