"""
perf_log_reader.py
-------------------
Lightweight helper used from a notebook to scrape the [PERF] lines that
the production code writes into visor.log after each profiled API call,
and save them as a self-describing JSON report.

Supports multiple operation namespaces so the same reader can be used for
different API methods (e.g. ``update_variables`` or ``add_dataset``).
The ``namespace`` argument controls:
  - which top-level [PERF] line is expected (for ``total_s`` validation)
  - the output JSON filename prefix

No reimplementation of the call chain — this only reads the log.

Usage in notebook (update_variables):
    from ansys.visor.viewer.utils.perf_log_reader import PerfLogReader

    reader = PerfLogReader(report_dir="../../benchmark_results/update_variables")

    reader.mark()
    vis.update_variables(dataset_id, [...])
    json_path = reader.save_report(dataset_label=Path(DATASET_FILE).name)
    print(json_path.name)

Usage in notebook (add_dataset):
    reader = PerfLogReader(
        report_dir="../../benchmark_results/add_dataset",
        namespace="add_dataset",
    )

    reader.mark()
    vis.add_dataset(DATASET_FILE)
    json_path = reader.save_report(dataset_label=Path(DATASET_FILE).name)
    print(json_path.name)
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ansys.visor.viewer.config import settings

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches any [PERF] line, capturing:
#   label  — everything after "[PERF] " up to the first " | " (or end of line)
#   phases — the rest of the line after the first " | " separator (may be empty)
_RE_PERF_LINE = re.compile(
    r"\[PERF\]\s+(?P<label>[^|]+?)(?:\s+\|\s+(?P<phases>.+))?$"
)

# Extracts all  key=value  or  key=<float>s  pairs from the phases segment.
# Matches:  word_chars=  followed by digits/dot  with an optional trailing 's'
_RE_KV = re.compile(r"([\w.+\-']+)=([0-9.]+)s?")

# ---------------------------------------------------------------------------
# Label → canonical phase-key mapping
#
# Keys in this dict are the *label* strings that PerfTimer writes
# (i.e. the text between "[PERF] " and the first " | ").
# Values map each phase name from the log to the key stored in report["phases"].
#
# Adding a new phase to PerfTimer requires no regex changes — only an entry
# here (and optionally in _PHASE_DISPLAY_LABELS below) if you want a
# human-readable label in the TXT report.
# ---------------------------------------------------------------------------

# Each entry: log_label_prefix -> {phase_name_in_log: key_in_report_phases}
# Use a prefix match (startswith) so labels with variable content work,
# e.g. "_update_variable 'pressure'" matches "_update_variable".
_LABEL_PHASE_MAP: list[tuple[str, dict[str, str]]] = [
    ("update_variables ", {
        "from_dict":                    "from_dict_total_s",
        "update_variables_for_dataset": "update_variables_for_dataset_s",
        "total":                        "total_s",
    }),
    ("VisorDataset.update_variables ", {
        "validate":     "validate_total_s",
        "vtk_set_loop": "vtk_set_loop_total_s",
        "reload":       "reload_variables_total_s",
    }),
    ("update_variables_for_dataset ", {
        "dataset_registry.update":  "registry_update_s",
        "update_descendant_parts": "update_descendant_parts_s",
        "render":                   "render_scene_s",
    }),
    ("add_dataset", {
        "resolve_io":     "resolve_io_s",
        "add_to_scene":   "add_to_scene_s",
        "finalize_scene": "finalize_scene_s",
        "total":          "total_s",
    }),
    ("render", {
        "RenderWindow.Render": "render1_window_render_s",
        "LocalView.update":    "render1_local_view_update_s",
    }),
]

# ---------------------------------------------------------------------------
# Namespace → profile configuration
#
# Each entry describes how PerfLogReader behaves for a given operation
# namespace:
#   file_prefix:    prefix for the output JSON filename
#   total_key:      the phases dict key that must be present for a valid report
# ---------------------------------------------------------------------------
_NAMESPACE_CONFIG: dict[str, dict] = {
    "update_variables": {
        "file_prefix": "update_variables_profile",
        "total_key":   "total_s",
    },
    "add_dataset": {
        "file_prefix": "add_dataset_profile",
        "total_key":   "total_s",
    },
}

def _match_label(label: str) -> dict[str, str] | None:
    """Return the phase-key mapping for this label, or None if unrecognised."""
    for prefix, mapping in _LABEL_PHASE_MAP:
        if label.startswith(prefix) or label.strip() == prefix.strip():
            return mapping
    return None




def _get_environment() -> dict:
    """Return a dict with versions of Python, VTK, NumPy, and OS platform info."""
    try:
        from vtkmodules.vtkCommonCore import vtkVersion
        vtk_ver = vtkVersion.GetVTKVersion()
    except Exception:
        vtk_ver = "unknown"
    return {
        "python": sys.version,
        "vtk":    vtk_ver,
        "numpy":  np.__version__,
        "os":     platform.platform(),
    }


class PerfLogReader:
    """
    Reads [PERF] timing lines from visor.log after each production call and
    writes a per-run JSON report.

    Parameters
    ----------
    report_dir:
        Directory where JSON reports are written.
    log_path:
        Path to visor.log. Defaults to the standard location under
        settings.default_log_dir.
    target_s:
        Performance target in seconds used for the meets_target flag.
    namespace:
        The operation being profiled.  Controls the report filename prefix and
        which phases key is used to validate that perf logging was active.
        Supported values: ``"update_variables"`` (default) or ``"add_dataset"``.
    """

    def __init__(
        self,
        report_dir: str | os.PathLike = ".",
        log_path: str | os.PathLike | None = None,
        target_s: float = 0.1,
        namespace: str = "update_variables",
    ):
        if namespace not in _NAMESPACE_CONFIG:
            raise ValueError(
                f"Unknown namespace {namespace!r}. "
                f"Choose one of: {list(_NAMESPACE_CONFIG)}"
            )
        self._report_dir = Path(report_dir)
        self._report_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = Path(log_path) if log_path else Path(settings.default_log_dir) / "visor.log"
        self._target_s = target_s
        self._namespace = namespace
        self._ns_cfg = _NAMESPACE_CONFIG[namespace]
        self._mark_pos: int = 0  # byte offset in log file at last mark()

    def mark(self) -> None:
        """
        Record the current end-of-file position in the log.
        Call this immediately BEFORE the profiled API call
        (e.g. ``vis.update_variables()`` or ``vis.add_dataset()``).
        """
        if self._log_path.exists():
            self._mark_pos = self._log_path.stat().st_size
        else:
            self._mark_pos = 0

    def save_report(
        self,
        dataset_label: str = "",
        mesh_info: dict | None = None,
    ) -> Path:
        """
        Read the [PERF] lines appended since mark(), build a JSON report,
        and write it to report_dir.

        Call this immediately AFTER the profiled API call (and after the
        client-side updates have completed in the browser, if you want
        client-side timings).

        Parameters
        ----------
        dataset_label:
            Filename of the dataset (e.g. 'vtk_object_sphere_r1028_v4_c3_z2.vtp').
            Stored in the report so the aggregator can reconstruct matrix axes.
        mesh_info:
            Optional dict with 'num_points' and 'num_cells'.  If None, derived
            from the per-variable records (n_tuples from _update_variable lines)
            when available.

        Returns
        -------
        Path
            Path to the written JSON file.
        """
        new_lines = self._read_new_lines()
        report    = self._parse_lines(new_lines)

        total_key = self._ns_cfg["total_key"]
        if total_key not in report["phases"]:
            raise RuntimeError(
                f"No [PERF] lines for namespace '{self._namespace}' were found in the log "
                "since the last mark(). "
                "Perf logging may not be enabled — add 'perf_logging: true' to "
                "your .visor config file and restart the server before retrying."
            )

        self._build_report(report, dataset_label, mesh_info)

        ts        = datetime.fromisoformat(report["timestamp"]).strftime("%Y%m%dT%H%M%S")
        prefix    = self._ns_cfg["file_prefix"]
        json_path = self._report_dir / f"{prefix}_{ts}.json"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return json_path

    def _build_report(self, report: dict, dataset_label: str, mesh_info: dict | None) -> None:
        """Annotate a parsed report dict with metadata, mesh info, and derived fields."""
        report["dataset_label"] = dataset_label
        report["namespace"]     = self._namespace
        report["timestamp"]     = datetime.now(tz=timezone.utc).isoformat()
        report["environment"]   = _get_environment()
        report["target_s"]      = self._target_s
        total_key               = self._ns_cfg["total_key"]
        report["total_s"]       = report["phases"].get(total_key, 0.0)
        report["meets_target"]  = report["total_s"] <= self._target_s

        if mesh_info:
            report["mesh_info"] = mesh_info
        elif report["variables"]:
            report["mesh_info"] = {"num_points": report["variables"][0]["n_tuples"]}

        report["num_points"] = (
            report["mesh_info"].get("num_points", 0) if report.get("mesh_info") else 0
        )
        report["total_elements"] = sum(
            v["n_tuples"] * v["n_components"] for v in report["variables"]
        )


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_new_lines(self) -> list[str]:
        """Return only the lines appended to the log since mark()."""
        if not self._log_path.exists():
            return []
        with open(self._log_path, encoding="utf-8", errors="replace") as f:
            f.seek(self._mark_pos)
            return f.read().splitlines()

    def _parse_lines(self, lines: list[str]) -> dict:
        """
        Parse [PERF] lines into a structured report dict.

        Each line is dispatched to a focused _parse_* helper based on its
        label.  Adding or renaming a phase only requires updating
        _LABEL_PHASE_MAP — no per-line-type regex to touch here.
        """
        phases: dict[str, float | int] = {}
        variables: list[dict] = []
        client: dict = {}

        for line in lines:
            m = _RE_PERF_LINE.search(line)
            if not m:
                continue
            label      = m.group("label").strip()
            phases_str = m.group("phases") or ""
            kv         = {k: v for k, v in _RE_KV.findall(phases_str)}
            self._parse_line(label, phases_str, kv, phases, variables, client)

        return {
            "phases":        phases,
            "variables":     variables,
            "client":        client,
            "num_variables": int(phases.pop("n_vars", len(variables))),
        }

    def _parse_line(
        self,
        label: str,
        phases_str: str,
        kv: dict[str, str],
        phases: dict,
        variables: list,
        client: dict,
    ) -> None:
        """Dispatch one parsed [PERF] line to the appropriate handler."""
        if label == "client updateAsync":
            client.update(self._parse_client_wasm_line(phases_str, kv))
        elif label == "client onServerUpdateAsync":
            client.update(self._parse_client_server_update_line(kv))
        elif label.startswith("_update_variable "):
            variables.append(self._parse_variable_line(label, kv))
        else:
            self._parse_server_phase_line(label, kv, phases)

    @staticmethod
    def _parse_client_wasm_line(phases_str: str, kv: dict[str, str]) -> dict:
        """Parse the 'client updateAsync' [PERF] line from the browser."""
        result = {
            "total_ms":    float(kv.get("total",  0)),
            "wasm_ms":     float(kv.get("wasm",   0)),
            "resize_ms":   float(kv.get("resize", 0)),
            "state_count": int(float(kv.get("states", 0))),
            "blob_count":  int(float(kv.get("blobs",  0))),
        }
        # MB values appear in the log line in a fixed order:
        #   states=N (X MB) | blobs=N (Y MB total, largest=Z MB in ...ms)
        mb_keys  = ("state_total_mb", "blob_total_mb", "blob_max_mb")
        mb_vals  = re.findall(r"([\d.]+)\s*MB", phases_str)
        for key, val in zip(mb_keys, mb_vals):
            result[key] = float(val)
        dur_m = re.search(r"in\s+([\d.]+)ms", phases_str)
        result["blob_max_dur_ms"] = float(dur_m.group(1)) if dur_m else 0.0
        return result

    @staticmethod
    def _parse_client_server_update_line(kv: dict[str, str]) -> dict:
        """Parse the 'client onServerUpdateAsync' [PERF] line from the browser."""
        return {"handler_ms": float(kv.get("handler", 0))}

    @staticmethod
    def _parse_variable_line(label: str, kv: dict[str, str]) -> dict:
        """Parse a per-variable '_update_variable ...' [PERF] line."""
        label_kv = {k: v for k, v in _RE_KV.findall(label)}
        name_m   = re.search(r"'([^']+)'", label)
        name     = name_m.group(1) if name_m else label
        n_tuples     = int(label_kv.get("n_tuples", 0))
        n_components = int(label_kv.get("n_components", 1))
        return {
            "name":           name,
            "n_tuples":       n_tuples,
            "n_components":   n_components,
            "set_loop_s":     float(kv.get("set_loop+modified", 0.0)),
            "total_elements": n_tuples * n_components,
        }

    @staticmethod
    def _parse_server_phase_line(label: str, kv: dict[str, str], phases: dict) -> None:
        """Parse a standard server-side [PERF] phase line into the phases dict."""
        phase_map = _match_label(label)
        if phase_map is None:
            return  # unrecognised label — ignore silently
        for log_key, report_key in phase_map.items():
            if log_key in kv:
                phases[report_key] = float(kv[log_key])
        # n_vars is embedded in the label of the top-level update_variables lines
        if label.startswith("update_variables ") or label.startswith("VisorDataset.update_variables "):
            label_kv = {k: v for k, v in _RE_KV.findall(label)}
            if "n_vars" in label_kv:
                phases["n_vars"] = int(label_kv["n_vars"])




