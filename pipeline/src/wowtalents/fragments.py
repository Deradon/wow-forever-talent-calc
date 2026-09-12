"""Access to single fragments of the live YouTube DASH stream (stage 0).

The format-299 ``url`` in the yt-dlp info.json plus ``&sq=N`` returns one
self-contained fragment that covers stream second N (verified 2026-09-13:
``sq=11000`` decodes with PTS 11000.5 s). The URL carries ``expire=`` and is
refreshed with ``yt-dlp -j`` into ``work/probe/info.refreshed.json``; the
download's own ``work/video/*.info.json`` is never written.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path

import requests

VIDEO_ID = "DxtVEhjyROU"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"

PIPELINE_DIR = Path(__file__).resolve().parents[2]
WORK = PIPELINE_DIR / "work"
VIDEO_DIR = WORK / "video"
INFO_JSON = VIDEO_DIR / "xaryu-blizzcon-day1.info.json"
DOWNLOAD_LOG = VIDEO_DIR / "download.log"
PROBE_DIR = WORK / "probe"
REFRESHED_INFO_JSON = PROBE_DIR / "info.refreshed.json"

REFRESH_CMD = [
    "uvx", "--python", "3.12", "--from", "yt-dlp@latest", "yt-dlp",
    "--js-runtimes", "node", "--live-from-start", "-j", VIDEO_URL,
]


class FragmentError(Exception):
    """A fragment request did not yield a decodable fragment."""


def hms(t: float) -> str:
    """Seconds -> ``HH:MM:SS`` (floored)."""
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def parse_hms(s: str) -> int:
    """``HH:MM:SS`` / ``MM:SS`` / plain seconds -> int seconds."""
    parts = [int(p) for p in str(s).split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def format_url(info: dict, format_id: str = "299") -> str:
    """Return the fragment base URL of ``format_id`` from a yt-dlp info dict.

    ``requested_formats`` is checked first (present when yt-dlp selected the
    format), then ``formats``.
    """
    for key in ("requested_formats", "formats"):
        for f in info.get(key) or []:
            if f.get("format_id") == format_id and f.get("url"):
                return f["url"]
    raise KeyError(f"format {format_id} with a url not found in info.json")


def url_expiry(url: str) -> dt.datetime | None:
    m = re.search(r"[?&]expire=(\d+)", url)
    if not m:
        return None
    return dt.datetime.fromtimestamp(int(m.group(1)), tz=dt.timezone.utc)


def best_fragment_url(
    format_id: str = "299",
    candidates: tuple[Path, ...] = (REFRESHED_INFO_JSON, INFO_JSON),
) -> tuple[str, Path]:
    """Pick the candidate info.json whose URL expires last."""
    best: tuple[str, Path, dt.datetime] | None = None
    for path in candidates:
        if not path.exists():
            continue
        try:
            url = format_url(json.loads(path.read_text()), format_id)
        except (KeyError, ValueError):
            continue
        exp = url_expiry(url) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        if best is None or exp > best[2]:
            best = (url, path, exp)
    if best is None:
        raise FileNotFoundError("no info.json with a usable fragment URL")
    return best[0], best[1]


def refresh_info(dest: Path = REFRESHED_INFO_JSON, timeout: int = 300) -> dict:
    """Run ``yt-dlp -j`` (no download) and store the fresh info dict at ``dest``."""
    proc = subprocess.run(REFRESH_CMD, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise FragmentError(f"yt-dlp refresh failed ({proc.returncode}): {proc.stderr[-800:]}")
    info = json.loads(proc.stdout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(proc.stdout)
    return info


def fetch_fragment(url: str, sq: int, session: requests.Session | None = None,
                   timeout: float = 30) -> bytes:
    """GET fragment ``sq``; raise FragmentError on non-200 or empty body."""
    sess = session or requests
    r = sess.get(f"{url}&sq={sq}", timeout=timeout)
    if r.status_code != 200:
        raise FragmentError(f"HTTP {r.status_code} for sq={sq}")
    if len(r.content) < 1000:
        raise FragmentError(f"fragment sq={sq} too small ({len(r.content)} bytes)")
    return r.content


def decode_frame(data: bytes, width: int | None = 640, fmt: str = "jpg",
                 quality: int = 2, frame_index: int = 0) -> bytes:
    """Decode one video frame from a fragment via ffmpeg (stdin -> stdout).

    ``width`` None keeps the native resolution. ``fmt`` is ``jpg`` or ``png``.
    """
    vf = []
    if frame_index:
        vf.append(f"select=gte(n\\,{frame_index})")
    if width:
        vf.append(f"scale={width}:-1")
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", "pipe:0", "-frames:v", "1"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if fmt == "png":
        cmd += ["-f", "image2", "-c:v", "png"]
    else:
        cmd += ["-f", "image2", "-c:v", "mjpeg", "-q:v", str(quality)]
    cmd.append("pipe:1")
    proc = subprocess.run(cmd, input=data, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise FragmentError(f"ffmpeg failed: {proc.stderr.decode(errors='replace')[-400:]}")
    return proc.stdout


def skipped_fragments(log: Path = DOWNLOAD_LOG) -> int:
    """Number of 'Skipping fragment' lines in the running download's log (must stay 0)."""
    if not log.exists():
        return 0
    return log.read_bytes().count(b"Skipping fragment")


class FragmentClient:
    """Fetches fragments with a reusable session and URL refresh on expiry."""

    def __init__(self, format_id: str = "299", timeout: float = 30):
        self.format_id = format_id
        self.timeout = timeout
        self.session = requests.Session()
        self.url, self.source = best_fragment_url(format_id)

    @property
    def expiry(self) -> dt.datetime | None:
        return url_expiry(self.url)

    def refresh(self) -> None:
        info = refresh_info()
        self.url = format_url(info, self.format_id)
        self.source = REFRESHED_INFO_JSON

    def fetch(self, sq: int) -> bytes:
        return fetch_fragment(self.url, sq, self.session, self.timeout)


FRAGS_DIR = WORK / "frags"


class FragmentCache:
    """On-disk cache of raw fragments (``work/frags/<sq>.bin``) for stages 3 and 4.

    One request at a time, ``sleep`` seconds between network fetches, refresh
    the URL after ``max_failures`` consecutive failures, abort when the main
    download starts skipping fragments. Cached fragments cost no request.
    """

    def __init__(self, cache_dir: Path = FRAGS_DIR, sleep: float = 0.3, max_failures: int = 3,
                 client: FragmentClient | None = None):
        self.cache_dir = cache_dir
        self.sleep = sleep
        self.max_failures = max_failures
        self._client = client
        self.fetched = 0

    @property
    def client(self) -> FragmentClient:
        if self._client is None:
            self._client = FragmentClient()
        return self._client

    def path(self, sq: int) -> Path:
        return self.cache_dir / f"{sq}.bin"

    def get(self, sq: int) -> bytes:
        p = self.path(sq)
        if p.exists():
            return p.read_bytes()
        if skipped_fragments():
            raise FragmentError("download.log shows skipped fragments; not touching the stream")
        failures = 0
        refreshed = False
        while True:
            try:
                data = self.client.fetch(sq)
                break
            except Exception as e:  # noqa: BLE001
                failures += 1
                if failures >= self.max_failures:
                    if refreshed:
                        raise FragmentError(f"sq={sq}: still failing after a URL refresh: {e}") from e
                    self.client.refresh()
                    refreshed = True
                    failures = 0
                time.sleep(max(self.sleep, 1.0))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self.fetched += 1
        time.sleep(self.sleep)
        return data
