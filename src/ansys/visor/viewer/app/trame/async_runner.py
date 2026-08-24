"""Class that allows running coroutines in a background thread, and waiting for them
to finish synchronously."""

import asyncio
import re
import threading
import weakref
from asyncio import AbstractEventLoop, Future
from concurrent.futures import Future as ConcurrentFuture
from threading import Event, Thread
from typing import Coroutine


class AsyncRunner:
    """
    `AsyncRunner` provides a non-invasive way to synchronously wait for coroutines
    to finish. It does this by handing coroutines off to a dedicated background
    thread, and returns a Future that completes when the coroutine is finished.
    It is non-invasive because it does not modify nor use the event loop that
    may be running in the main thread, nor does it create an event loop in the
    main thread.
    """

    def __init__(self):
        self.__error_regex_pattern = re.compile(r"\b(?:set_wakeup_fd|aiohttp)\b", re.IGNORECASE)
        self.__thread: Thread | None = None
        self.__loop: AbstractEventLoop | None = None

    def __ensure_thread_and_loop(self) -> None:
        if self.__thread is not None:
            return
        loop: AbstractEventLoop | None = None
        loop_set_event = Event()
        startup_error: BaseException | None = None

        def thread_target():
            nonlocal loop, startup_error
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop_set_event.set()
                loop.run_forever()
            except BaseException as e:
                startup_error = e
            finally:
                loop_set_event.set()

        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()
        while not loop_set_event.wait(timeout=0.2):
            pass
        if startup_error:
            raise startup_error
        if loop is None:
            raise RuntimeError("Event loop cannot be None")
        self.__thread = thread
        self.__loop = loop

    @property
    def thread(self) -> Thread:
        """Gets the background thread."""
        self.__ensure_thread_and_loop()
        return self.__thread

    async def run_coroutine_async(self, coroutine: Coroutine, patch_return_future: bool) -> any:
        """
        Offloads a provided coroutine to run on a background thread asynchronously.

        Args:
            coroutine (Coroutine): The coroutine to run on the background thread.
            patch_return_future (bool): If `coroutine` itself returns a Future or Task object, this
                                    specifies whether that awaitable object should be "patched" to allow
                                    you to `await` it in the main thread. For example, if `coroutine`
                                    itself returns a `Task` object, you will be able to `await` that `Task`
                                    in the main thread without getting the error: `Task got Future attached
                                    to a different loop`.

        Returns:
            any: The result of the coroutine.
        """
        concurrent_future: ConcurrentFuture = self.run_coroutine(coroutine, patch_return_future)
        # Use asyncio.wrap_future() to convert the "concurrent.futures.Future" (which is
        # non-awaitable) into an "asyncio.Future" (which is awaitable).
        return await asyncio.wrap_future(concurrent_future)

    def run_coroutine_block(self, coroutine: Coroutine, patch_return_future: bool) -> any:
        """
        Offloads a provided coroutine to run on a background thread. Works in both synchronous
        and asynchronous contexts. Blocks the thread until the coroutine is finished.

        Args:
            coroutine (Coroutine): The coroutine to run on the background thread.
            patch_return_future (bool): If `coroutine` itself returns a Future or Task object, this
                                    specifies whether that awaitable object should be "patched" to allow
                                    you to `await` it in the main thread. For example, if `coroutine`
                                    itself returns a `Task` object, you will be able to `await` that `Task`
                                    in the main thread without getting the error: `Task got Future attached
                                    to a different loop`.

        Returns:
            any: The result of the coroutine.
        """
        concurrent_future: ConcurrentFuture = self.run_coroutine(coroutine, patch_return_future)
        condition = threading.Condition()
        with condition:
            while not condition.wait_for(lambda: concurrent_future.done(), timeout=0.2):
                pass
            e = concurrent_future.exception()
            if e:
                raise e
        return concurrent_future.result()

    def run_coroutine(self, coroutine: Coroutine, patch_return_future: bool) -> ConcurrentFuture:
        """
        Offloads a provided coroutine to run on a background thread. Works in both synchronous
        and asynchronous contexts. Returns a concurrent.futures.Future that completes when the
        coroutine is finished.

        Args:
            coroutine (Coroutine): The coroutine to run on the background thread.
            patch_return_future (bool): If `coroutine` itself returns a Future or Task object, this
                                    specifies whether that awaitable object should be "patched" to allow
                                    you to `await` it in the main thread. For example, if `coroutine`
                                    itself returns a `Task` object, you will be able to `await` that `Task`
                                    in the main thread without getting the error: `Task got Future attached
                                    to a different loop`.

        Returns:
            concurrent.futures.Future: A concurrent.futures.Future that completes when the coroutine is
            finished. The result of the future is the result of the coroutine. If `patch_return_future` is
            True` and `coroutine` returned a `Future` or `Task`, the result of the coroutine will be
            another coroutine that can be awaited in the main thread without error.
        """
        self.__ensure_thread_and_loop()
        current_loop: AbstractEventLoop | None = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        if current_loop is self.__loop:
            raise RuntimeError(("The provided event loop cannot be the same as the event"
                                " loop associated with the current thread."))

        async def outer_coroutine():
            result: any
            try:
                result = await coroutine
            except BaseException as e:
                for element in e.args:
                    if isinstance(element, str) and self.__error_regex_pattern.match(element):
                        # Append helpful information to the existing error message if
                        # the message contains keywords listed in the regex pattern.
                        msg = (
                            "Caught an error related to 'set_wakeup_fd()' or 'aiohttp'. If you are trying to start a\n"
                            " Trame server, ensure you are passing the background thread to the 'server.start()'\n"
                            " method, like this: 'server.start(thread=async_runner.thread)'. The following is the\n"
                            f" original exception information:\n{e.args[0]}"
                        )
                        e.args = (msg,)
                raise
            if patch_return_future:
                # If the coroutine that we ran on the background thread returns a Future (this includes Tasks),
                # then "patch" it so that it can be awaited in the main thread without error. We do this by
                # creating a concurrent.futures.Future (a.k.a. ConcurrentFuture) object that resolves when the
                # background thread's return Future resolves. We then return a coroutine that wraps the
                # ConcurrentFuture into an asyncio.Future and awaits it. This allows us to await the background
                # thread's Future from a different thread, without getting the "Task got Future attached to a
                # different loop" error.
                if not isinstance(result, Future):
                    raise RuntimeError("coroutine must return a Future if patch_return_future is True")
                res_fut: Future = result
                con_fut = ConcurrentFuture()
                res_fut.add_done_callback(lambda _: con_fut.set_result(res_fut.result()))

                async def patch():
                    return await asyncio.wrap_future(con_fut)

                coro = patch()
                # Register the coroutine to be closed when it is garbage collected.
                # This fixes the "coroutine was never awaited" warning (it's OK if the
                # coroutine was never awaited).
                weakref.finalize(coro, coro.close)
                return coro
            return result

        return asyncio.run_coroutine_threadsafe(outer_coroutine(), self.__loop)

    def dispose(self):
        """Stops the background thread and closes the event loop."""
        if self.__loop is None:
            return
        self.__loop.call_soon_threadsafe(self.__loop.stop)
        if self.__thread is not None:
            self.__thread.join(timeout=2)
        self.__loop.close()
        self.__loop = None
        self.__thread = None
