"""Cross-stack parity test: the Python ``VisorVtkVariableType`` enum's
member values must agree with the frontend's ``FIELD_ASSOCIATIONS`` literal
in ``VisorVtkDataArray.tsx``.

The TypeScript file is read as text and parsed for its ``FIELD_ASSOCIATIONS``
literal -- it is not executed (no jest/node toolchain is invoked here); this
is the "stub" side of the cross-stack check. If the file cannot be found,
this test fails loudly (no ``skipif``/try-except swallowing the error).
"""

import re
from pathlib import Path

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType

_TSX_RELATIVE_PATH = (
    "src/ansys/visor/visor-client/src/state/appstate/vtkInfo/VisorVtkDataArray.tsx"
)


def _repo_root() -> Path:
    """Walk up from this file until a directory containing the TS file's
    root-relative path is found."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _TSX_RELATIVE_PATH
        if candidate.is_file():
            return parent
    raise FileNotFoundError(
        f"Could not locate {_TSX_RELATIVE_PATH!r} above {here}"
    )


def _extract_field_associations(text: str) -> set:
    match = re.search(r"const\s+FIELD_ASSOCIATIONS\s*=\s*\[([^]]*)\]", text)
    assert match, "FIELD_ASSOCIATIONS literal not found in VisorVtkDataArray.tsx"
    items = re.findall(r"'([^']*)'|\"([^\"]*)\"", match.group(1))
    return {a or b for a, b in items}


def test_python_enum_values_match_frontend_field_associations():
    tsx_path = _repo_root() / _TSX_RELATIVE_PATH
    text = tsx_path.read_text(encoding="utf-8")

    extracted = _extract_field_associations(text)

    # The literal must actually contain entries, and the stated size (2:
    # POINT, CELL) must hold, before comparing set contents.
    assert len(extracted) > 0
    assert len(extracted) == 2

    python_values = {member.value for member in VisorVtkVariableType}
    assert python_values == extracted

