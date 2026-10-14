"""Validate SDK preparation boundaries before running the feature tests."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prepare_pipecat", ROOT / "scripts/prepare_pipecat.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_given_pinned_sdk_when_preparing_twice_then_source_is_untouched_and_output_is_stable(
    tmp_path,
):
    source = ROOT / "pipecat"
    before = MODULE.source_hashes(source)
    destination = tmp_path / "sdk"

    first = MODULE.prepare(source, destination, ROOT / "patches/pipecat")
    second = MODULE.prepare(source, destination, ROOT / "patches/pipecat")

    assert first == second
    assert MODULE.source_hashes(source) == before
    assert "10-lazy-trace.patch" in first["patch_sha256"]
    assert json.loads((destination / MODULE.MARKER).read_text()) == first
    assert (
        first["output_sha256"]["src/pipecat/processors/frame_processor.py"]
        != before["src/pipecat/processors/frame_processor.py"]
    )


def test_given_unmanaged_output_when_preparing_then_existing_files_are_preserved(
    tmp_path,
):
    destination = tmp_path / "sdk"
    destination.mkdir()
    note = destination / "keep.txt"
    note.write_text("existing work")

    with pytest.raises(ValueError, match="unmanaged"):
        MODULE.prepare(ROOT / "pipecat", destination, ROOT / "patches/pipecat")
    assert note.read_text() == "existing work"


def test_given_edited_generated_sdk_when_preparing_then_local_changes_are_preserved(
    tmp_path,
):
    destination = tmp_path / "sdk"
    MODULE.prepare(ROOT / "pipecat", destination, ROOT / "patches/pipecat")
    edited = destination / "src/pipecat/processors/frame_processor.py"
    edited.write_text(edited.read_text() + "\n# local edit\n")

    with pytest.raises(ValueError, match="local source edits"):
        MODULE.prepare(ROOT / "pipecat", destination, ROOT / "patches/pipecat")
    assert edited.read_text().endswith("# local edit\n")


@pytest.mark.parametrize("destination", [ROOT / "pipecat", ROOT])
def test_given_source_or_ancestor_when_preparing_then_replacement_is_rejected(
    destination,
):
    with pytest.raises(ValueError, match="separate"):
        MODULE.prepare(ROOT / "pipecat", destination, ROOT / "patches/pipecat")
