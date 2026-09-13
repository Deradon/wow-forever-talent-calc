"""Stream-time ranges out of the merged VOD (``work/video/*.mkv``).

The live download numbers fragments in stream seconds (``sq``); stages 3/4
work in that clock. The merged mkv starts at pts 0 but its first fragment does
not begin exactly at a whole stream second, so a frame at stream time ``t``
sits at file time ``t + OFFSET``. ``OFFSET`` was measured by matching the
probe sample of fragment 13680 (its first frame, stream time 13680.0) against
the decoded mkv: exact match (mean |diff| 0.0) at file time 13679.533.
:func:`measure_offset` repeats that measurement. Packet timestamps in the
ranges decoded so far are a constant 1/60 s apart (no gaps); :func:`pts_gaps`
checks a range before trusting the constant offset there.

Frames are streamed one at a time from ``ffmpeg -ss <t> -i <mkv> -t <dur>``
so a minutes-long range never sits in RAM.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from . import fragments as fr
from .ui import FRAME_H, FRAME_W

MKV = fr.WORK / "video" / "xaryu-blizzcon-day1.mkv"
OFFSET = -0.467          # file time minus stream time, seconds (see module docstring)
STREAM_FPS = 60


def file_time(stream_t: float, offset: float = OFFSET) -> float:
    """Stream seconds (fragment clock) -> seconds into the mkv."""
    return float(stream_t) + offset


def stream_time(file_t: float, offset: float = OFFSET) -> float:
    """Seconds into the mkv -> stream seconds."""
    return float(file_t) - offset


def split_sq(stream_t: float, fps: int = STREAM_FPS) -> tuple[int, int]:
    """Stream time -> ``(sq, frame offset)`` as stage 4 records them (fragment = 1 s)."""
    sq = int(np.floor(stream_t + 1e-6))
    off = int(round((stream_t - sq) * fps))
    if off >= fps:
        sq, off = sq + 1, 0
    return sq, off


def decode_cmd(mkv: Path, file_t0: float, duration: float, fps: int = STREAM_FPS,
               width: int = FRAME_W, height: int = FRAME_H) -> list[str]:
    """ffmpeg command streaming raw BGR frames of ``[file_t0, file_t0 + duration)`` at ``fps``."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{file_t0:.3f}", "-i", str(mkv),
           "-t", f"{duration:.3f}", "-vf", f"fps={fps}"]
    if (width, height) != (FRAME_W, FRAME_H):
        cmd[-1] += f",scale={width}:{height}"
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    return cmd


def frame_times(stream_t0: float, n: int, fps: int = STREAM_FPS) -> list[float]:
    """Stream time of the first ``n`` frames the decoder yields for a range starting at ``stream_t0``."""
    return [stream_t0 + k / fps for k in range(n)]


def decode_range(mkv: Path, stream_t0: float, stream_t1: float, fps: int = STREAM_FPS,
                 offset: float = OFFSET, width: int = FRAME_W, height: int = FRAME_H,
                 max_frames: int | None = None) -> Iterator[tuple[float, np.ndarray]]:
    """Yield ``(stream_t, bgr)`` for every decoded frame of ``[stream_t0, stream_t1)``.

    Frames arrive one at a time from ffmpeg's stdout pipe; the caller must not
    keep them (stage 4's :class:`~wowtalents.ui.RunTracker` keeps only the
    sharpest crop of a run).
    """
    duration = float(stream_t1) - float(stream_t0)
    if duration <= 0:
        return
    cmd = decode_cmd(mkv, file_time(stream_t0, offset), duration, fps, width, height)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdout is not None
    nbytes = width * height * 3
    k = 0
    try:
        while max_frames is None or k < max_frames:
            buf = proc.stdout.read(nbytes)
            if len(buf) < nbytes:
                break
            yield stream_t0 + k / fps, np.frombuffer(buf, np.uint8).reshape(height, width, 3)
            k += 1
    finally:
        proc.stdout.close()
        proc.kill() if proc.poll() is None else None
        proc.wait()


def packet_pts(mkv: Path, file_t0: float, duration: float) -> list[float]:
    """Video packet timestamps (sorted) of ``[file_t0, file_t0 + duration]`` via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
         "-of", "csv=p=0", "-read_intervals", f"{file_t0:.3f}%+{duration:.3f}", str(mkv)],
        capture_output=True, text=True, check=True).stdout
    return sorted(float(x) for x in out.split() if x.strip())


def pts_gaps(pts: Iterable[float], fps: int = STREAM_FPS, tol: float = 1.5) -> list[tuple[float, float]]:
    """``(pts, gap)`` wherever consecutive packets are more than ``tol`` frame periods apart.

    An empty list means the range is contiguous at ``fps`` and the constant
    stream-to-file offset holds throughout.
    """
    ts = sorted(pts)
    limit = tol / fps
    return [(a, round(b - a, 4)) for a, b in zip(ts, ts[1:]) if b - a > limit]


def best_match(ref: np.ndarray, frames: Iterable[tuple[float, np.ndarray]],
               roi: tuple[int, int, int, int] = (400, 0, 1780, 720)) -> tuple[float, float]:
    """``(file_t, mean |diff|)`` of the frame nearest ``ref`` inside ``roi`` (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = roi
    r = ref[y0:y1, x0:x1].astype(np.int16)
    best_t, best_d = float("nan"), float("inf")
    for t, f in frames:
        d = float(np.abs(f[y0:y1, x0:x1].astype(np.int16) - r).mean())
        if d < best_d:
            best_t, best_d = t, d
    return best_t, best_d


def measure_offset(mkv: Path, probe_png: Path, sq: int, window: float = 3.0, fps: int = STREAM_FPS) -> tuple[float, float]:
    """Re-measure ``OFFSET`` from a stage-0 native sample (first frame of fragment ``sq``).

    Decodes ``[sq - window, sq + window]`` of the mkv in file time and returns
    ``(offset, mean |diff| of the best frame)``; a good match is below 0.5.
    """
    import cv2

    ref = cv2.imread(str(probe_png))
    if ref is None:
        raise FileNotFoundError(probe_png)
    t0 = float(sq) - window
    frames = decode_range(mkv, t0, float(sq) + window, fps=fps, offset=0.0)   # offset 0: iterate in file time
    file_t, diff = best_match(ref, frames)
    return round(file_t - sq, 3), diff
