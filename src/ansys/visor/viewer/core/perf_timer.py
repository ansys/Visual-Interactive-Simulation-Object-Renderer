"""
perf_timer.py
-------------
Lightweight multi-phase wall-clock timer that emits a single ``[PERF]``
log line (compatible with PerfLogReader) only when **both** of the
following conditions are true:

1. ``perf_logging`` is enabled via the application settings
   (``settings.perf_logging``, set through the ``.visor`` config file) —
   the global on/off switch.
2. The ``PerfTimer`` was constructed with ``enabled=True`` (the default) —
   a per-call-site switch that lets you explicitly opt in only the APIs
   that have been fully instrumented, while still passing a no-op timer
   into shared helpers (e.g. ``_prepare_and_render_scene``) from
   un-instrumented call paths.

Usage
-----
    from ansys.visor.viewer.core.perf_timer import PerfTimer

    # Fully instrumented API — will record phases when perf_logging is on.
    timer = PerfTimer("VisorDataset.update_variables", logger, n_vars=3)

    with timer.phase("validate"):
        ...
    with timer.phase("vtk_set_loop"):
        ...
    with timer.phase("reload"):
        ...

    timer.log()
    # -> [PERF] VisorDataset.update_variables n_vars=3
    #    | validate=0.0012s | vtk_set_loop=0.0340s | reload=0.0008s

    # Shared helper that accepts an optional timer.  Un-instrumented callers
    # simply omit the argument; the helper creates a disabled no-op internally.
    def _prepare_and_render_scene(self, input, metadata, timer: PerfTimer = None):
        if timer is None:
            timer = PerfTimer.disabled()
        with timer.phase("finalize_scene"):
            ...

The ``[PERF]`` line format intentionally matches the regex patterns in
``ansys.visor.viewer.utils.perf_log_reader`` so that PerfLogReader can
parse reports without any changes.

When either gate is off, both ``timer.phase()`` and ``timer.log()`` are
no-ops with negligible overhead.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from ansys.visor.viewer.config import settings


class PerfTimer:
    """
    Multi-phase wall-clock timer that produces a single ``[PERF]`` log line.

    Parameters
    ----------
    label:
        Text placed immediately after ``[PERF]``.
        E.g. ``"VisorDataset.update_variables"`` or
        ``"_update_variable 'pressure'"``
    logger:
        Any logger with an ``info(str)`` method (typically a
        ``VisorDefaultLogger`` instance).
    enabled:
        Per-call-site opt-in flag.  Set to ``False`` for APIs that have not
        yet been instrumented but still need to pass a no-op timer into a
        shared helper.  Defaults to ``True`` so that existing instrumented
        call sites are unaffected.  Recording only happens when *both* this
        flag and ``settings.perf_logging`` are ``True``.
    **extra_fields:
        Key/value pairs appended to the label segment before the phase
        timings, e.g. ``n_vars=3`` or ``n_tuples=1024``.

    Notes
    -----
    ``settings.perf_logging`` is evaluated when each ``PerfTimer`` is
    constructed (i.e. on each call-site invocation), not at module import
    time.  This means a ``.visor`` config change takes effect on the next
    server start without any code changes.
    """

    __slots__ = ("_label", "_logger", "_extra", "_phases", "_enabled")

    @classmethod
    def disabled(cls) -> "PerfTimer":
        """
        Return a no-op timer.

        Used inside shared helpers that accept an optional ``timer`` argument
        to normalise ``None`` into a safe no-op, so every downstream
        ``timer.phase()`` call can be written unconditionally::

            def _prepare_and_render_scene(self, input, metadata,
                                          timer: PerfTimer = None):
                if timer is None:
                    timer = PerfTimer.disabled()
                with timer.phase("finalize_scene"):
                    ...

        Un-instrumented callers simply omit ``timer=`` — they do **not** need
        to construct ``PerfTimer.disabled()`` themselves.  The returned
        instance never records phases or emits log lines regardless of the
        global ``settings.perf_logging`` flag.
        """
        return cls("", logger=None, enabled=False)

    def __init__(self, label: str, logger=None, *, enabled: bool = True, **extra_fields):
        """Initialize the timer."""
        self._label = label
        self._logger = logger
        self._extra: dict = extra_fields
        self._phases: list[tuple[str, float]] = []
        # Both gates must be open: the global config flag AND the explicit
        # per-call-site opt-in.
        self._enabled: bool = enabled and settings.perf_logging

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """
        Context manager that times the enclosed block and records it as a
        named phase.  Is a no-op when perf logging is disabled.
        """
        if not self._enabled:
            yield
            return
        t0 = time.perf_counter()
        yield
        self._phases.append((name, time.perf_counter() - t0))

    def log(self, *, include_total: bool = False) -> None:
        """
        Emit the accumulated ``[PERF]`` line to the logger.
        Does nothing when perf logging is disabled.

        Parameters
        ----------
        include_total:
            When ``True``, appends a ``total=Xs`` field that is the sum of
            all recorded phases.  Useful when the caller wants a single
            top-level summary field (e.g. ``update_variables`` in the
            trame interface).
        """
        if not self._enabled or self._logger is None:
            return

        # Build the label segment: "[PERF] <label> key=val key=val ..."
        label_part = f"[PERF] {self._label}"
        for k, v in self._extra.items():
            label_part += f" {k}={v}"

        # Build phase segments: "phase_name=0.0000s"
        phase_parts = [f"{name}={elapsed:.4f}s" for name, elapsed in self._phases]

        if include_total:
            total = sum(elapsed for _, elapsed in self._phases)
            phase_parts.append(f"total={total:.4f}s")

        self._logger.info(" | ".join([label_part] + phase_parts))

