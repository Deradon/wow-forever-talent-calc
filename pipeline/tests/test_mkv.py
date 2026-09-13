"""Pure helpers of ``wowtalents.mkv`` and ``stages/04b_hovers_mkv.py`` (no video, no ffmpeg)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wowtalents import mkv  # noqa: E402

_spec = importlib.util.spec_from_file_location("stage4b", ROOT / "stages" / "04b_hovers_mkv.py")
st4b = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(st4b)


def test_file_and_stream_time_round_trip():
    # measured: the first frame of fragment 13680 sits at file time 13679.533
    assert mkv.file_time(13680) == 13680 + mkv.OFFSET
    assert abs(mkv.file_time(13680) - 13679.533) < 1e-9
    assert mkv.stream_time(mkv.file_time(14825.5)) == 14825.5
    assert mkv.file_time(100, offset=-2.0) == 98.0


def test_split_sq_matches_stage4_fragment_clock():
    assert mkv.split_sq(14825.0) == (14825, 0)
    assert mkv.split_sq(14825 + 20 / 60) == (14825, 20)
    assert mkv.split_sq(14825.9999) == (14826, 0)      # rounding never yields offset 60
    assert mkv.split_sq(14825 + 59 / 60) == (14825, 59)


def test_decode_cmd_seeks_before_input_and_streams_raw_bgr():
    cmd = mkv.decode_cmd(Path("v.mkv"), 14824.533, 150.0, fps=60)
    assert cmd.index("-ss") < cmd.index("-i")            # input seeking: fast and frame-accurate
    assert cmd[cmd.index("-ss") + 1] == "14824.533"
    assert cmd[cmd.index("-t") + 1] == "150.000"
    assert cmd[cmd.index("-vf") + 1] == "fps=60"
    assert cmd[-3:] == ["-pix_fmt", "bgr24", "pipe:1"] and "rawvideo" in cmd
    small = mkv.decode_cmd(Path("v.mkv"), 0.0, 1.0, fps=15, width=640, height=360)
    assert small[small.index("-vf") + 1] == "fps=15,scale=640:360"


def test_frame_times_follow_the_fps_grid():
    ts = mkv.frame_times(14825.0, 3, fps=60)
    assert ts[0] == 14825.0 and abs(ts[2] - (14825 + 2 / 60)) < 1e-9
    assert mkv.frame_times(10.0, 2, fps=1) == [10.0, 11.0]


def test_pts_gaps_reports_only_missing_frames():
    pts = [0.533 + k / 60 for k in range(120)]
    assert mkv.pts_gaps(pts) == []
    broken = pts[:50] + [t + 0.5 for t in pts[50:]]     # half a second missing after frame 49
    g = mkv.pts_gaps(broken)
    assert len(g) == 1 and abs(g[0][0] - pts[49]) < 1e-9 and abs(g[0][1] - (0.5 + 1 / 60)) < 1e-3
    assert mkv.pts_gaps(reversed(pts)) == []             # order does not matter
    assert mkv.pts_gaps([]) == [] and mkv.pts_gaps([1.0]) == []


def test_best_match_picks_the_nearest_frame_inside_the_roi():
    rng = np.random.default_rng(0)
    ref = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
    other = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
    near = ref.copy()
    near[100:200, 500:600] = 0                           # small change inside the ROI
    outside = ref.copy()
    outside[900:1000, 100:300] = 255                     # change outside the ROI: still an exact match
    t, d = mkv.best_match(ref, [(1.0, other), (2.0, near), (3.0, outside)])
    assert t == 3.0 and d == 0.0
    t, d = mkv.best_match(ref, [(1.0, other), (2.0, near)])
    assert t == 2.0 and 0 < d < 5


def test_mkv_segment_id_keeps_stage5_shape():
    sid = st4b.mkv_segment_id(7, "mage", 14825)
    assert sid == "m07-mage-14825"
    # stage 5's hover_docs matches ``*-<class>-*.json`` and filters on the first/last dash-separated parts
    assert sid.split("-")[1] == "mage" and sid.split("-")[-1] == "14825"


def test_borrowed_calib_relabels_but_keeps_the_donor_files():
    donor = {"segment_id": "07-mage-14850", "t_start": 14850, "t_end": 14900, "frames_used": [14850, 14851],
             "cells": [{"tree": 1}], "files": {"median": "07-mage-14850-median.png"}, "page": "Primary"}
    out = st4b.borrowed_calib(donor, "m07-mage-14825", 14825, 14975, "mkv 04:07:05-04:09:35")
    assert out["segment_id"] == "m07-mage-14825" and (out["t_start"], out["t_end"]) == (14825, 14975)
    assert out["borrowed_from"] == "07-mage-14850" and out["files"] == donor["files"]
    assert out["frames_used"] == [] and out["cells"] == donor["cells"]
    assert donor["segment_id"] == "07-mage-14850"      # donor untouched
