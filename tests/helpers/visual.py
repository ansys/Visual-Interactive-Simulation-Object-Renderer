# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest


@dataclass(frozen=True)
class VisualCheckResult:
    """Result of a visual comparison."""
    name: str
    passed: bool
    rms: float
    current_path: Path
    baseline_path: Path
    diff_path: Optional[Path]
    message: str = ""


@dataclass(frozen=True)
class TestResult:
    """Aggregates results from multiple visual checks."""
    # make sure any amount of VisualCheckResults are allowed in the checks tuple
    checks: tuple[VisualCheckResult, ...]

    @property
    def passed(self) -> bool:
        """Return True only if all checks have passed."""
        for check in self.checks:
            if not check.passed:
                return False
        return True

    @property
    def failed_checks(self) -> list[VisualCheckResult]:
        """Return all checks that did not pass."""
        failed = []
        for check in self.checks:
            if not check.passed:
                failed.append(check)
        return failed

    def summary(self) -> str:
        """Return a formatted summary of all visual checks for logging."""

        lines = []

        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            parts = [f"[{status}] {check.name}"]

            # RMS value
            if check.rms is not None:
                parts.append(f"RMS={check.rms:.3f}")

            # Additional message
            if check.message:
                parts.append(f"- {check.message}")

            # Paths for failed checks
            if not check.passed:
                if check.current_path:
                    parts.append(f"current={check.current_path}")
                if check.baseline_path:
                    parts.append(f"baseline={check.baseline_path}")
                if check.diff_path:
                    parts.append(f"diff={check.diff_path}")

            line = " | ".join(parts)
            lines.append(line)

        return "\n".join(lines)

def make_test_result(*checks: VisualCheckResult) -> TestResult:

    """
    Convenience factory to build a TestResult from multiple CheckResults.
    """
    return TestResult(checks=tuple(checks))


def verify_canvas_against_baseline(
    *,
    canvas_locator,                 # Playwright locator: e.g., page.locator("canvas.vtk-wasm-1")
    baseline_dir: Path,             # pytest fixture-provided baseline dir (Path) for image canonicals
    pixel_threshold: float,         # pytest fixture-provided threshold for image comparison
    request,                        # pytest's request fixture (to read --update-baseline)
    compare_images,                 # perform comparison
    test_id,                        # ID used in filenames (customize per test)
    test_suite: str = "",           # Name of the test suite (e.g., "regressions") for organizing artifacts
    message: str = ""

) -> VisualCheckResult:

    """
    Take a screenshot of a canvas element, compare it to a baseline image, and assert

    Behavior:
      - Saves a timestamped current screenshot under tests/artifacts/{test_suite}
      - If `--update-baseline` is set or baseline doesn't exist, copies current -> baseline and skips the test.
      - Otherwise, compares current vs baseline with `compare_images` and asserts on failure.

    Args:
        canvas_locator: Playwright locator already pointing to the canvas to capture.
        baseline_dir: Directory where baseline images are stored (e.g., tests/reference_images)
        pixel_threshold: RMS threshold used by compare_images.
        request: pytest's built-in request fixture to read CLI options (e.g., --update-baseline)
        compare_images: A callable function that performs image comparison:
            (current_path: Path, baseline_path: Path, diff_path: Path, threshold: float)
            -> tuple[bool, float, Optional[Path]]
        test_id: Stem used in filenames to distinguish different tests
        screenshots_root: Root folder for storing current and diff artifacts
        message: Custom message to add to the TestResult summary for additional context

    Returns:
        VisualCheckResult with pass/fail, RMS value, and artifact paths

    Raises:
        pytest.skip: If baseline is updated/initialized during this run
        AssertionError: If comparison fails the threshold.
    """
    # Ensure output directory exists
    screenshots_root = Path("tests", "artifacts", test_suite, "screenshots")
    screenshots_root.mkdir(parents=True, exist_ok=True)

    # Timestamped filenames
    stamp = time.strftime("%Y%m%d-%H%M%S")
    current_shot = screenshots_root / f"{test_id}_current_{stamp}.png"
    diff_path = screenshots_root / f"{test_id}_diff_{stamp}.png"
    baseline_shot = baseline_dir / f"{test_id}_baseline.png"

    # Capture screenshot of just the canvas element
    canvas_locator.screenshot(path=str(current_shot))

    # Baseline update behavior
    update_baseline = bool(request.config.getoption("--update-baseline"))
    if update_baseline or not baseline_shot.exists():
        baseline_shot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current_shot, baseline_shot)
        pytest.skip(
            f"Baseline {'initialized' if not baseline_shot.exists() else 'updated'} "
            f"for {test_id}; re-run without --update-baseline to validate."
        )

    # Compare and assert
    passed, rms, saved = compare_images(
        current_shot, baseline_shot, diff_path, threshold=pixel_threshold
    )

    return VisualCheckResult(
        passed=passed,
        rms=rms,
        current_path=current_shot,
        baseline_path=baseline_shot,
        diff_path=saved,
        name = test_id,
        message= message
    )
