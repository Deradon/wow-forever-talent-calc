"""``wowtalents.stagekit``: the helpers stages 11 and 12 used to carry a copy of each.

Round two's K-7 listed nine of them; the two copies of the confidence ladder in ``apply_third``
had already drifted apart in their matching rule, which is the reason these tests exist.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wowtalents import stagekit as SK  # noqa: E402


def test_hms_formats_stream_seconds():
    assert SK.hms(0) == "00:00:00"
    assert SK.hms(14375.4) == "03:59:35"


def test_parse_window_takes_both_spellings():
    assert SK.parse_window("14340-14520") == (14340, 14520)
    assert SK.parse_window("03:59:00-04:02:00") == (14340, 14520)
    assert SK.parse_window("59:00-1:02:00") == (3540, 3720)


def test_json_object_finds_a_fenced_answer_and_respects_the_key():
    text = 'Sure:\n```json\n{"entries": [{"name": "Attack"}]}\n```\nDone.'
    assert SK.json_object(text, "entries")["entries"][0]["name"] == "Attack"
    assert SK.json_object(text) == {"entries": [{"name": "Attack"}]}
    assert SK.json_object('{"other": 1}', "entries") is None
    assert SK.json_object("no json at all") is None


def test_json_object_skips_a_leading_object_that_lacks_the_key():
    assert SK.json_object('{"thinking": 1} then {"traits": []}', "traits") == {"traits": []}


def test_source_is_in_schema_key_order_and_omits_empty_extras():
    src = SK.source("vid", 1.2345, 74, "data/review/x.png", 0.6666, "qwen", "tooltip")
    assert list(src) == ["kind", "video", "t", "frame", "crop", "panel", "confidence", "reader",
                         "reviewed"]
    assert src["t"] == 1.234 and src["confidence"] == 0.67 and src["reviewed"] is False
    full = SK.source("vid", 1, 2, "c", 1.0, "r", "tooltip", [{"reader": "codex"}], "a note")
    assert full["readings"] == [{"reader": "codex"}] and full["note"] == "a note"


def _agree(a: dict, b: dict) -> float:
    if a == b:
        return 1.0
    return 0.7 if a.get("name") == b.get("name") else 0.3


def test_apply_third_runs_one_confidence_ladder():
    ident = lambda r: r.get("name") or ""          # noqa: E731
    recs = [{"name": "A", "confidence": 0.3, "readings": [{"name": "A"}, {"name": "A"}]},
            {"name": "B", "confidence": 1.0, "readings": [{"name": "B", "rank": 1}]},
            {"name": "C", "confidence": 0.3, "readings": [{"name": "C", "rank": 2}]}]
    third = [{"name": "A"}, {"name": "B", "rank": 2}, {"name": "D"}]
    out = SK.apply_third(recs, third, ident=ident, agreement=_agree)
    by = {r["name"]: r for r in out}
    # the third reading matches one pass verbatim, so the row is lifted to "two of three agree"
    assert by["A"]["confidence"] == SK.TWO_OF_THREE_VERBATIM
    # both passes agreed and the third reads it differently: capped, never raised
    assert by["B"]["confidence"] == SK.BOTH_PASSES_AGREE_THIRD_DIFFERS
    assert by["C"]["confidence"] == 0.3                             # untouched: no third reading
    assert by["D"]["confidence"] == SK.THIRD_ONLY                   # a lead, not a fact
    assert by["A"]["codex"] is True and "codex" not in by["C"]
    assert by["A"]["readings"] == [{"name": "A"}, {"name": "A"}, {"name": "A"}]


def test_apply_third_leaves_records_alone_when_the_third_read_nothing():
    recs = [{"name": "A", "confidence": 0.7, "readings": [{"name": "A"}]}]
    assert SK.apply_third(recs, [], ident=lambda r: r["name"], agreement=_agree) == recs


def test_prune_crops_keeps_underscore_context_crops_and_honours_dry_run(tmp_path):
    review = tmp_path / "data" / "review" / "spells" / "druid"
    review.mkdir(parents=True)
    for name in ("bear-form.png", "_page-druid-1.png", "gone.png"):
        (review / name).write_bytes(b"x")
    keep = {"data/review/spells/druid/bear-form.png"}
    spells = review.parent
    dry = SK.prune_crops(spells, keep, tmp_path, dry_run=True)
    assert dry == ["data/review/spells/druid/gone.png"]
    assert (review / "gone.png").is_file()                          # dry run deletes nothing
    gone = SK.prune_crops(spells, keep, tmp_path)
    assert gone == ["data/review/spells/druid/gone.png"]
    assert not (review / "gone.png").exists()
    assert (review / "_page-druid-1.png").is_file()
    assert (review / "bear-form.png").is_file()


def test_codex_opinion_returns_the_cached_answer_without_calling_out(tmp_path, monkeypatch):
    (tmp_path / "crop.codex.json").write_text(json.dumps({"entries": [{"name": "Cached"}]}))

    def explode(*a, **k):                                           # pragma: no cover - must not run
        raise AssertionError("codex was called although a cached answer exists")

    monkeypatch.setattr(SK.subprocess, "run", explode)
    assert SK.codex_opinion(tmp_path / "crop.png", tmp_path, "prompt", "entries") == \
        {"entries": [{"name": "Cached"}]}


def test_codex_opinion_survives_a_missing_cli(tmp_path, monkeypatch):
    def missing(*a, **k):
        raise OSError("no codex on this machine")

    monkeypatch.setattr(SK.subprocess, "run", missing)
    assert SK.codex_opinion(tmp_path / "crop.png", tmp_path, "prompt", "entries") is None


def test_now_is_the_stamp_every_generated_file_carries():
    import re
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", SK.now())


@pytest.mark.parametrize("bad", ["", "{", "{\"a\": }"])
def test_json_object_never_raises(bad):
    assert SK.json_object(bad) is None
