import asyncio
import threading
from concurrent.futures import Future as ConcurrentFuture

import pytest

from ansys.visor.viewer.app.trame.async_runner import AsyncRunner


@pytest.fixture
def runner():
    """Provide an AsyncRunner instance."""
    r = AsyncRunner()
    yield r
    r.dispose()

def test_thread_and_loop_created_once(runner):
    """Verify that the thread instance is created only once."""
    thread1 = runner.thread
    thread2 = runner.thread
    assert thread1 is thread2
    assert isinstance(thread1, threading.Thread)
    assert thread1.is_alive()

@pytest.mark.asyncio
async def test_run_coroutine_async_simple(runner):
    """Verify that a coroutine can be executed asynchronously."""
    async def coro():
        await asyncio.sleep(0.01)
        return 42
    result = await runner.run_coroutine_async(coro(), patch_return_future=False)
    assert result == 42

def test_run_coroutine_block_simple(runner):
    """Verify that a coroutine can be executed synchronously."""
    async def coro():
        await asyncio.sleep(0.01)
        return "done"
    result = runner.run_coroutine_block(coro(), patch_return_future=False)
    assert result == "done"

def test_run_coroutine_returns_concurrent_future(runner):
    """Verify that run_coroutine returns a concurrent future."""
    async def coro():
        return "future"
    fut = runner.run_coroutine(coro(), patch_return_future=False)
    assert isinstance(fut, ConcurrentFuture)
    assert fut.result() == "future"

def test_run_coroutine_block_exception(runner):
    """Verify that synchronous execution propagates coroutine exceptions."""
    async def coro():
        raise ValueError("fail")
    with pytest.raises(ValueError, match="fail"):
        runner.run_coroutine_block(coro(), patch_return_future=False)

@pytest.mark.asyncio
async def test_run_coroutine_async_exception(runner):
    """Verify that asynchronous execution propagates coroutine exceptions."""
    async def coro():
        raise RuntimeError("async fail")
    with pytest.raises(RuntimeError, match="async fail"):
        await runner.run_coroutine_async(coro(), patch_return_future=False)

def test_patch_return_future(runner):
    """Verify that returned futures can be patched into awaitable coroutines."""
    async def inner():
        await asyncio.sleep(0.01)
        return 123
    async def outer():
        fut = asyncio.ensure_future(inner())
        return fut
    # patch_return_future=True returns a coroutine
    patched = runner.run_coroutine(outer(), patch_return_future=True).result()
    # patched is a coroutine, can be awaited
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(patched)
    assert result == 123
    loop.close()

def test_dispose_stops_and_closes_loop(runner):
    """Verify that disposal stops and closes the event loop."""
    # Should not raise
    runner.dispose()
    # Dispose again is a no-op
    runner.dispose()

def test_thread_is_daemon(runner):
    """Verify that the runner thread is configured as a daemon."""
    assert runner.thread.daemon

def test_thread_is_alive_after_creation(runner):
    """Verify that the runner thread is alive after creation."""
    assert runner.thread.is_alive()
