# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def ensure_same_size_and_mode(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    if a.size != b.size:
        # Resize A to match B to avoid false failures if canvas sizing changes slightly
        a = a.resize(b.size, Image.Resampling.LANCZOS)
    # Images work better when converted to RGB
    a = a.convert("RGB")
    b = b.convert("RGB")

    return a, b

def rms_diff(a: Image.Image, b: Image.Image):
    """
    Compute Root Mean Square difference between two images (0..255).
    requires tuning
    """
    diff = ImageChops.difference(a, b)
    # Calculate statistics for resultant diff image
    stat = ImageStat.Stat(diff)

    rms = math.sqrt(sum(s**2 for s in stat.mean) / len(stat.mean))
    # diff is supplied to be able to upload as a package on failure
    return rms, diff

def compare_images(current_path: Path, baseline_path: Path, diff_out: Path, threshold: float) -> tuple[bool, float, Path | None]:
    """
    Return (passed, rms_value, diff_path_if_fail).
    """
    with Image.open(current_path) as curr, Image.open(baseline_path) as base:
        curr, base = ensure_same_size_and_mode(curr, base)
        curr = curr.copy()
        base = base.copy()
    rms, diff = rms_diff(curr, base)
    if rms > threshold:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
        diff.save(diff_out)
        return False, rms, diff_out
    return True, rms, None
