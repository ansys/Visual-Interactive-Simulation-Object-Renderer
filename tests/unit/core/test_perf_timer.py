
from ansys.visor.viewer.core.perf_timer import PerfTimer

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

class DummyLogger:
    """ A simple logger that records messages for testing purposes."""
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)


# ------------------------------------------------------------------
# disabled()
# ------------------------------------------------------------------

def test_disabled_timer_is_noop():
    """disabled() should create a timer that does nothing."""

    timer = PerfTimer.disabled()

    # phase should not record anything
    with timer.phase("x"):
        pass

    # log should not fail or emit anything
    timer.log()

    assert True  # no-op behavior (no exceptions)


# ------------------------------------------------------------------
# phase recording
# ------------------------------------------------------------------

def test_phase_records_when_enabled(monkeypatch):
    """phase should record elapsed time when enabled."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        True,
    )

    # control perf_counter
    times = iter([1.0, 2.0])
    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.time.perf_counter",
        lambda: next(times),
    )

    timer = PerfTimer("label", logger=DummyLogger())

    with timer.phase("test"):
        pass

    # internal behavior exercised via log output
    timer.log()

    assert len(timer._phases) == 1
    assert timer._phases[0][0] == "test"
    assert abs(timer._phases[0][1] - 1.0) < 1e-6


def test_phase_is_noop_when_disabled(monkeypatch):
    """phase should not record when disabled."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        False,
    )

    timer = PerfTimer("label", logger=DummyLogger())

    with timer.phase("test"):
        pass

    assert timer._phases == []


# ------------------------------------------------------------------
# logging behavior
# ------------------------------------------------------------------

def test_log_emits_expected_format(monkeypatch):
    """log should emit correctly formatted message."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        True,
    )

    times = iter([1.0, 2.0])
    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.time.perf_counter",
        lambda: next(times),
    )

    logger = DummyLogger()
    timer = PerfTimer("my.label", logger, foo=1)

    with timer.phase("p"):
        pass

    timer.log()

    assert len(logger.messages) == 1
    msg = logger.messages[0]

    assert "[PERF] my.label foo=1" in msg
    assert "p=1.0000s" in msg


def test_log_includes_total(monkeypatch):
    """log should include total when requested."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        True,
    )

    times = iter([1.0, 2.0, 3.0, 5.0])  # two phases: 1s + 2s
    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.time.perf_counter",
        lambda: next(times),
    )

    logger = DummyLogger()
    timer = PerfTimer("label", logger)

    with timer.phase("a"):
        pass
    with timer.phase("b"):
        pass

    timer.log(include_total=True)

    msg = logger.messages[0]

    assert "a=1.0000s" in msg
    assert "b=2.0000s" in msg
    assert "total=3.0000s" in msg


def test_log_skips_when_disabled(monkeypatch):
    """log should not emit when logging disabled."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        False,
    )

    logger = DummyLogger()
    timer = PerfTimer("label", logger)

    with timer.phase("x"):
        pass

    timer.log()

    assert logger.messages == []


def test_log_skips_without_logger(monkeypatch):
    """log should not emit when logger is None."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        True,
    )

    timer = PerfTimer("label", logger=None)

    with timer.phase("x"):
        pass

    # should not error
    timer.log()

    assert True


# ------------------------------------------------------------------
# extra fields
# ------------------------------------------------------------------

def test_extra_fields_in_label(monkeypatch):
    """Extra fields should be appended to label."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        True,
    )

    times = iter([1.0, 2.0])
    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.time.perf_counter",
        lambda: next(times),
    )

    logger = DummyLogger()
    timer = PerfTimer("label", logger, a=1, b=2)

    with timer.phase("p"):
        pass

    timer.log()

    msg = logger.messages[0]

    assert "a=1" in msg
    assert "b=2" in msg


# ------------------------------------------------------------------
# enabled flag interaction
# ------------------------------------------------------------------

def test_enabled_flag_overrides_global(monkeypatch):
    """Per-instance enabled=False should disable recording even if global is True."""

    monkeypatch.setattr(
        "ansys.visor.viewer.core.perf_timer.settings.perf_logging",
        True,
    )

    timer = PerfTimer("label", logger=DummyLogger(), enabled=False)

    with timer.phase("x"):
        pass

    timer.log()

    assert timer._phases == []
