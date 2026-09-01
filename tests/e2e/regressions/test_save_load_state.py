# (c)2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.
"""End-to-end regression tests for the save/load state feature.

These tests verify that Visor can serialize its viewer state (scene graph,
datasets) to disk and restore it correctly, preserving datasets and keeping
the WebGL canvas functional throughout the round-trip.

save_state is async (it requests state from the frontend via websocket) so we
schedule it on the Trame background event loop via the server manager's
AsyncRunner. load_state is sync and can be called directly.
"""

import json
from pathlib import Path

import pytest

from tests.helpers.utils.canvas import (
    assert_canvas_alive,
    goto_and_wait,
    settle,
    wait_for_canvas,
    wait_for_webgl,
)


def _save_state_sync(visor, state_dir: str, force_snapshot: bool = False) -> None:
    """Call the async save_state on the Trame event loop, blocking until done.

    Parameters
    ----------
    force_snapshot : bool
        If True, mark all datasets as dirty so snapshots are always written
        to state_dir regardless of prior save history.
    """
    if force_snapshot:
        for dataset in visor._scene.datasets.values():
            dataset.is_dirty = True
    runner = visor._server_manager._async_runner
    runner.run_coroutine_block(visor.save_state(state_dir), False)


@pytest.mark.regression
class TestSaveLoadState:
    """Regression tests for save/load state functionality."""

    def test_save_state_creates_artifacts(self, visor_server, page, tmp_path):
        """save_state should create visor.json and at least one vtkhdf snapshot."""
        state_dir = str(tmp_path / "state")
        Path(state_dir).mkdir()

        # Frontend must be connected for save_state to retrieve state via websocket
        goto_and_wait(page, visor_server.url)
        wait_for_canvas(page)
        wait_for_webgl(page)

        _save_state_sync(visor_server, state_dir)

        state_file = Path(state_dir) / "visor.json"
        assert state_file.exists(), "visor.json was not created by save_state"

        content = json.loads(state_file.read_text())
        assert isinstance(content, dict), "visor.json should contain a JSON object"
        assert "version" in content, "visor.json should contain a version field"

        vtkhdf_files = list(Path(state_dir).glob("*.vtkhdf"))
        assert len(vtkhdf_files) >= 1, "Expected at least one .vtkhdf snapshot file"

    def test_save_load_roundtrip_datasets_preserved(self, visor_server, page, tmp_path):
        """Datasets should be preserved across a save/load round-trip."""
        state_dir = str(tmp_path / "state")
        Path(state_dir).mkdir()

        # Frontend must be connected for save_state
        goto_and_wait(page, visor_server.url)
        wait_for_canvas(page)
        wait_for_webgl(page)

        datasets_before = visor_server.list_datasets()
        names_before = {ds["name"] for ds in datasets_before.values()}
        assert len(names_before) > 0, "Expected at least one dataset loaded initially"

        _save_state_sync(visor_server, state_dir)
        visor_server.load_state(state_dir)

        datasets_after = visor_server.list_datasets()
        names_after = {ds["name"] for ds in datasets_after.values()}

        assert names_before == names_after, (
            f"Dataset names changed after round-trip: before={names_before}, after={names_after}"
        )

    def test_save_load_canvas_still_alive(self, visor_server, page, tmp_path):
        """Canvas should remain functional after save and load operations."""
        url = visor_server.url
        state_dir = str(tmp_path / "state")
        Path(state_dir).mkdir()

        goto_and_wait(page, url)
        wait_for_canvas(page)
        wait_for_webgl(page)
        assert_canvas_alive(page, "before save_state")

        _save_state_sync(visor_server, state_dir)
        settle(page, ms=300)
        assert_canvas_alive(page, "after save_state")

        visor_server.load_state(state_dir)
        settle(page, ms=500)
        assert_canvas_alive(page, "after load_state")

    def test_save_load_state_file_content_valid(self, visor_server, page, tmp_path):
        """The state file should contain valid structure with expected fields."""
        state_dir = str(tmp_path / "state")
        Path(state_dir).mkdir()

        # Frontend must be connected for save_state
        goto_and_wait(page, visor_server.url)
        wait_for_canvas(page)
        wait_for_webgl(page)

        _save_state_sync(visor_server, state_dir)

        state_file = Path(state_dir) / "visor.json"
        content = json.loads(state_file.read_text())

        # Verify top-level structure
        assert content.get("version") == "1.0", "State version should be 1.0"
        assert "scene" in content, "State should contain scene data"
        assert "dataset_states" in content["scene"], "Scene should contain dataset_states"
        assert len(content["scene"]["dataset_states"]) > 0, (
            "dataset_states should not be empty"
        )

        # Verify each dataset state references a snapshot path
        for name, ds_state in content["scene"]["dataset_states"].items():
            snapshot_path = ds_state.get("serialized_dataset_path")
            assert snapshot_path is not None, (
                f"Dataset '{name}' missing serialized_dataset_path"
            )
            assert len(snapshot_path) > 0, (
                f"Dataset '{name}' has empty serialized_dataset_path"
            )

    def test_load_state_into_empty_scene(self, visor_server, page, tmp_path):
        """Loading state into an empty scene should restore datasets from snapshots.

        NOTE: This test must run last because it removes all datasets
        before restoring them.
        """
        state_dir = str(tmp_path / "state")
        Path(state_dir).mkdir()

        # Frontend must be connected for save_state
        goto_and_wait(page, visor_server.url)
        wait_for_canvas(page)
        wait_for_webgl(page)

        # Save current state (with dataset) - force_snapshot ensures .vtkhdf files
        # are written even if a prior test's save marked datasets clean
        _save_state_sync(visor_server, state_dir, force_snapshot=True)

        # Remove all datasets to empty the scene
        dataset_ids = list(visor_server.list_datasets().keys())
        for dataset_id in dataset_ids:
            visor_server.remove_dataset(dataset_id)

        empty_datasets = visor_server.list_datasets()
        assert len(empty_datasets) == 0, "Scene should be empty after removing all datasets"

        # Restore from saved state - load_state should restore from vtkhdf snapshots
        visor_server.load_state(state_dir)

        restored_datasets = visor_server.list_datasets()
        assert len(restored_datasets) > 0, "Datasets should be restored after load_state"

        # Verify canvas is functional with restored scene
        goto_and_wait(page, visor_server.url)
        wait_for_canvas(page)
        wait_for_webgl(page, timeout_ms=15_000)
        assert_canvas_alive(page, "after load_state into empty scene")
