"""Atomic writes (wowtalents.fsio) and the candidates record-count guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wowtalents import fsio  # noqa: E402


def test_write_text_atomic_writes_content_and_creates_parents(tmp_path: Path):
    dest = tmp_path / "deep" / "nested" / "out.txt"
    assert fsio.write_text_atomic(dest, "hello\n") == dest
    assert dest.read_text(encoding="utf-8") == "hello\n"


def test_write_json_atomic_matches_the_pipeline_serialisation(tmp_path: Path):
    dest = tmp_path / "doc.json"
    fsio.write_json_atomic(dest, {"a": 1, "name": "Nature's Grace"})
    assert dest.read_text(encoding="utf-8") == json.dumps({"a": 1, "name": "Nature's Grace"}, indent=2,
                                                          ensure_ascii=False) + "\n"


def test_a_failing_write_leaves_the_previous_content_and_no_temp_file(tmp_path: Path):
    dest = tmp_path / "candidates.json"
    fsio.write_json_atomic(dest, {"candidates": [1, 2, 3]})

    class Boom:
        def __str__(self):  # json.dumps raises before anything is written
            raise RuntimeError("boom")

    with pytest.raises(TypeError):
        fsio.write_json_atomic(dest, {"candidates": {Boom()}})
    assert json.loads(dest.read_text())["candidates"] == [1, 2, 3]
    assert [p.name for p in tmp_path.iterdir()] == ["candidates.json"]


def test_write_text_atomic_cleans_up_when_the_replace_target_is_a_directory(tmp_path: Path):
    dest = tmp_path / "adir"
    dest.mkdir()
    with pytest.raises(OSError):
        fsio.write_text_atomic(dest, "x")
    assert [p.name for p in tmp_path.iterdir()] == ["adir"]   # no .adir.*.tmp left behind


def test_write_text_atomic_replaces_in_one_step(tmp_path: Path):
    dest = tmp_path / "out.txt"
    dest.write_text("old", encoding="utf-8")
    fsio.write_text_atomic(dest, "new content that is much longer than the old one")
    assert dest.read_text(encoding="utf-8") == "new content that is much longer than the old one"


@pytest.mark.parametrize("doc,n", [({"candidates": [1, 2]}, 2), ([1, 2, 3], 3), ({}, 0), ([], 0), ({"candidates": None}, 0)])
def test_candidate_count_handles_both_document_shapes(doc, n):
    assert fsio.candidate_count(doc) == n


def test_write_candidates_atomic_refuses_a_shrinking_rewrite(tmp_path: Path):
    dest = tmp_path / "mage.candidates.json"
    fsio.write_json_atomic(dest, {"candidates": [{"id": "a"}, {"id": "b"}, {"id": "c"}]})
    with pytest.raises(ValueError, match="3 -> 2"):
        fsio.write_candidates_atomic(dest, {"candidates": [{"id": "a"}, {"id": "b"}]}, before=3)
    assert len(json.loads(dest.read_text())["candidates"]) == 3


def test_write_candidates_atomic_allows_same_or_growing(tmp_path: Path):
    dest = tmp_path / "mage.candidates.json"
    fsio.write_candidates_atomic(dest, {"candidates": [{"id": "a"}]}, before=0)
    fsio.write_candidates_atomic(dest, {"candidates": [{"id": "a"}, {"id": "b"}]}, before=1)
    assert len(json.loads(dest.read_text())["candidates"]) == 2


def test_write_text_atomic_keeps_the_destinations_mode(tmp_path: Path):
    """mkstemp makes 0600 files; an atomic rewrite must not quietly restrict a tracked file."""
    import os
    import stat
    dest = tmp_path / "tracked.json"
    dest.write_text("{}", encoding="utf-8")
    os.chmod(dest, 0o644)
    fsio.write_json_atomic(dest, {"a": 1})
    assert stat.S_IMODE(dest.stat().st_mode) == 0o644


def test_write_text_atomic_new_file_respects_umask(tmp_path: Path):
    import os
    import stat
    old = os.umask(0o022)
    try:
        dest = tmp_path / "fresh.json"
        fsio.write_json_atomic(dest, {"a": 1})
        assert stat.S_IMODE(dest.stat().st_mode) == 0o644
    finally:
        os.umask(old)
