from dataclasses import asdict

from ansys.visor.viewer.vtk.datasets.part_index import PartEntry, PartIndex


def test_part_entry_stores_fields_correctly():
    """PartEntry should store provided field values correctly."""
    entry = PartEntry(part_id=10, name="blockA", flat_index=3)

    assert entry.part_id == 10
    assert entry.name == "blockA"
    assert entry.flat_index == 3


def test_part_entry_equality():
    """PartEntry instances with same values should be equal."""
    e1 = PartEntry(part_id=1, name="A", flat_index=0)
    e2 = PartEntry(part_id=1, name="A", flat_index=0)

    assert e1 == e2


def test_part_entry_asdict_conversion():
    """PartEntry should convert cleanly to dict via dataclasses.asdict."""
    entry = PartEntry(part_id=5, name="my_part", flat_index=7)

    result = asdict(entry)

    assert result == {
        "part_id": 5,
        "name": "my_part",
        "flat_index": 7,
    }


# ------------------------------------------------------------------
# PartIndex tests
# ------------------------------------------------------------------

def test_non_composite_creates_single_part(monkeypatch):
    """Non-composite datasets should produce a single part."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 123,
    )

    data = object()
    idx = PartIndex(data, dataset_name="ds")

    parts = idx.list_parts()

    assert len(parts) == 1
    assert parts[0]["name"] == "ds"
    assert parts[0]["part_id"] == 123


def test_seed_id_is_used_when_available(monkeypatch):
    """Seed IDs should override random ID generation."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 999,
    )

    idx = PartIndex(object(), dataset_name="A", seed_ids=[42])

    parts = idx.list_parts()

    assert parts[0]["part_id"] == 42


def test_get_entry_returns_correct_entry(monkeypatch):
    """get_entry should return the correct PartEntry."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 7,
    )

    idx = PartIndex(object(), dataset_name="x")

    entry = idx.get_entry(7)

    assert entry is not None
    assert entry.name == "x"


def test_get_entry_returns_none_for_missing_id(monkeypatch):
    """get_entry should return None for unknown part IDs."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 1,
    )

    idx = PartIndex(object(), dataset_name="x")

    assert idx.get_entry(999) is None


def test_name_to_id_and_id_to_name_maps(monkeypatch):
    """Maps should reflect current part assignments."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 55,
    )

    idx = PartIndex(object(), dataset_name="abc")

    assert idx.name_to_id_map == {"abc": 55}
    assert idx.id_to_name_map == {55: "abc"}


def test_part_ids_property(monkeypatch):
    """part_ids should list all assigned IDs."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 88,
    )

    idx = PartIndex(object(), dataset_name="x")

    assert idx.part_ids == [88]


def test_get_leaf_block_non_composite_returns_data(monkeypatch):
    """Non-composite get_leaf_block should return the original data."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 5,
    )

    data = object()
    idx = PartIndex(data, dataset_name="x")

    result = idx.get_leaf_block(5, data)

    assert result is data


def test_get_leaf_block_invalid_id_returns_none(monkeypatch):
    """get_leaf_block should return None for invalid part ID."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )

    idx = PartIndex(object(), dataset_name="x")

    assert idx.get_leaf_block(999, object()) is None


def test_composite_iteration_builds_multiple_parts(monkeypatch):
    """Composite datasets should build entries for each leaf."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: True,
    )

    ids = iter([1, 2])
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: next(ids),
    )

    class FakeMeta:
        def __init__(self, name):
            self._name = name

        def Has(self, key): # noqa: N802
            return True

        def Get(self, key): # noqa: N802
            return self._name

    class FakeIterator:
        def __init__(self):
            self.items = ["A", "B"]
            self.index = 0

        def SkipEmptyNodesOn(self): pass # noqa: N802
        def IsDoneWithTraversal(self): return self.index >= len(self.items) # noqa: N802
        def GetCurrentMetaData(self): return FakeMeta(self.items[self.index]) # noqa: N802
        def GoToNextItem(self): self.index += 1 # noqa: N802
        def GetCurrentDataObject(self): return self.items[self.index] # noqa: N802

    class FakeComposite:
        def NewIterator(self): # noqa: N802
            return FakeIterator()

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.vtkCompositeDataSet",
        type("X", (), {"NAME": staticmethod(lambda: "NAME")}),
    )

    idx = PartIndex(FakeComposite())
    parts = idx.list_parts()

    assert len(parts) == 2
    assert {p["name"] for p in parts} == {"A", "B"}


def test_get_leaf_block_composite_advances_iterator(monkeypatch):
    """get_leaf_block should advance iterator based on flat_index."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: True,
    )

    ids = iter([10, 20])
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: next(ids),
    )

    class FakeMeta:
        def __init__(self, name):
            self._name = name

        def Has(self, key): # noqa: N802
            return True

        def Get(self, key): # noqa: N802
            return self._name

    class TrackingIterator:
        def __init__(self):
            self.items = ["block0", "block1"]
            self.index = 0
            self.advance_calls = 0

        def SkipEmptyNodesOn(self): pass # noqa: N802

        def IsDoneWithTraversal(self): # noqa: N802
            return self.index >= len(self.items)

        def GetCurrentMetaData(self): # noqa: N802
            return FakeMeta(self.items[self.index])

        def GoToNextItem(self): # noqa: N802
            self.index += 1
            self.advance_calls += 1

        def GetCurrentDataObject(self): # noqa: N802
            return self.items[self.index]

    class FakeComposite:
        def NewIterator(self): # noqa: N802
            return TrackingIterator()  # FIXED: new instance every time

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.vtkCompositeDataSet",
        type("X", (), {"NAME": staticmethod(lambda: "NAME")}),
    )

    data = FakeComposite()
    idx = PartIndex(data)

    # preserve insertion order instead of sorting
    second_part_id = idx.part_ids[1]

    result = idx.get_leaf_block(second_part_id, data)

    assert result == "block1"

def test_duplicate_names_emit_warning(monkeypatch):
    """Duplicate part names should trigger a logger warning."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: True,
    )

    # deterministic IDs (values don't matter here)
    ids = iter([1, 2])
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: next(ids),
    )

    class FakeMeta:
        def __init__(self, name):
            self._name = name

        def Has(self, key): # noqa: N802
            return True

        def Get(self, key): # noqa: N802
            return self._name

    class FakeIterator:
        def __init__(self):
            # duplicate names
            self.items = ["dup", "dup"]
            self.index = 0

        def SkipEmptyNodesOn(self): pass # noqa: N802

        def IsDoneWithTraversal(self): # noqa: N802
            return self.index >= len(self.items)

        def GetCurrentMetaData(self): # noqa: N802
            return FakeMeta(self.items[self.index])

        def GoToNextItem(self): # noqa: N802
            self.index += 1

    class FakeComposite:
        def NewIterator(self): # noqa: N802
            return FakeIterator()

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.vtkCompositeDataSet",
        type("X", (), {"NAME": staticmethod(lambda: "NAME")}),
    )

    warnings = []

    def fake_warning(msg):
        warnings.append(msg)

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.logger.warning",
        fake_warning,
    )

    PartIndex(FakeComposite())

    assert len(warnings) == 1
    assert "Duplicate part name 'dup'" in warnings[0]


# ------------------------------------------------------------------
# Positional seed (T1, T4, T5, T6)
# ------------------------------------------------------------------

def _patch_composite(monkeypatch, names):
    """Patch part_index so PartIndex traverses a fake composite with *names*."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: True,
    )

    class FakeMeta:
        def __init__(self, name):
            self._name = name

        def Has(self, key): # noqa: N802
            return True

        def Get(self, key): # noqa: N802
            return self._name

    class FakeIterator:
        def __init__(self):
            self.items = list(names)
            self.index = 0

        def SkipEmptyNodesOn(self): pass # noqa: N802

        def IsDoneWithTraversal(self): # noqa: N802
            return self.index >= len(self.items)

        def GetCurrentMetaData(self): # noqa: N802
            return FakeMeta(self.items[self.index])

        def GoToNextItem(self): # noqa: N802
            self.index += 1

        def GetCurrentDataObject(self): # noqa: N802
            return self.items[self.index]

    class FakeComposite:
        def NewIterator(self): # noqa: N802
            return FakeIterator()

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.vtkCompositeDataSet",
        type("X", (), {"NAME": staticmethod(lambda: "NAME")}),
    )

    return FakeComposite()


def _capture_errors(monkeypatch):
    """Collect logger.error records emitted by part_index."""

    errors = []
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.logger.error",
        lambda msg: errors.append(msg),
    )
    return errors


def test_colliding_seed_with_duplicate_names_keeps_both_parts(monkeypatch):
    """Two leaves sharing a name must still get the two seeded IDs, in order.

    This is the production configuration: duplicate names *and* a seed.  The
    name->id map collapses to one entry; the part index must not.
    """

    data = _patch_composite(monkeypatch, ["dup", "dup"])
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 999,
    )

    idx = PartIndex(data, dataset_name="ds", seed_ids=[101, 202])

    assert len(idx.part_ids) == 2
    assert idx.part_ids == [101, 202]
    assert len(idx.name_to_id_map) == 1


def test_seed_id_zero_is_honoured(monkeypatch):
    """Seed ID 0 is a valid JavaScript-safe integer and must not fall through."""

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.is_composite_dataset",
        lambda data: False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 999,
    )

    idx = PartIndex(object(), dataset_name="ds", seed_ids=[0])

    assert idx.part_ids == [0]


def test_short_seed_logs_error_and_falls_back(monkeypatch):
    """A seed shorter than the leaf count logs one error and degrades to random."""

    data = _patch_composite(monkeypatch, ["a", "b", "c"])
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 777,
    )
    errors = _capture_errors(monkeypatch)

    idx = PartIndex(data, dataset_name="ds", seed_ids=[101, 202])

    assert len(idx.part_ids) == 3
    assert idx.part_ids[0] == 101
    assert idx.part_ids[1] == 202
    assert idx.part_ids[2] == 777
    assert len(errors) == 1
    assert "seed length 2" in errors[0]
    assert "leaf count 3" in errors[0]


def test_long_seed_logs_error(monkeypatch):
    """A seed longer than the leaf count logs the same error: the check is an equality."""

    data = _patch_composite(monkeypatch, ["a", "b"])
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.part_index.get_random_javascript_safe_id",
        lambda: 777,
    )
    errors = _capture_errors(monkeypatch)

    idx = PartIndex(data, dataset_name="ds", seed_ids=[101, 202, 303])

    assert idx.part_ids == [101, 202]
    assert len(errors) == 1
    assert "seed length 3" in errors[0]
    assert "leaf count 2" in errors[0]

