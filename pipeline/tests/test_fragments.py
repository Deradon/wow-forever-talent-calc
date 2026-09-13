import json

from wowtalents import fragments as fr


def test_hms_roundtrip():
    assert fr.hms(13680) == "03:48:00"
    assert fr.parse_hms("03:48:00") == 13680
    assert fr.parse_hms("48:00") == 2880
    assert fr.parse_hms("77") == 77


def test_format_url_prefers_requested_formats():
    info = {
        "formats": [{"format_id": "299", "url": "https://a/?expire=1"}],
        "requested_formats": [{"format_id": "299", "url": "https://b/?expire=2"}],
    }
    assert fr.format_url(info) == "https://b/?expire=2"
    assert fr.url_expiry("https://b/?expire=2").timestamp() == 2


def test_best_fragment_url_picks_latest_expiry(tmp_path):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(json.dumps({"formats": [{"format_id": "299", "url": "https://x/?expire=100"}]}))
    new.write_text(json.dumps({"formats": [{"format_id": "299", "url": "https://y/?expire=200"}]}))
    url, src = fr.best_fragment_url(candidates=(old, new))
    assert url.startswith("https://y/") and src == new


def _log(tmp_path, text: str):
    p = tmp_path / "download.log"
    p.write_bytes(text.encode())
    return p


def test_classify_skips_live_edge_vs_throttled(tmp_path):
    log = _log(tmp_path, "[download] frag 1/3\rERROR: Did not get any data blocks\n"
                         "[download] fragment not found; Skipping fragment 30806 ...\n"
                         "[download] frag 2/3\nERROR: unable to download: HTTP Error 403: Forbidden\n"
                         "[download] Skipping fragment 30900 ...\n")
    assert fr.classify_skips(log) == (1, 1)
    assert fr.skipped_fragments(log) == 2


def test_download_health_aborts_on_throttled_and_new_live_edge_skips(tmp_path):
    import pytest
    log = _log(tmp_path, "ERROR: Did not get any data blocks\n[download] fragment not found; Skipping fragment 1 ...\n")
    h = fr.DownloadHealth(log)
    assert "1 live-edge skip" in h.check()          # pre-existing: warn only
    with log.open("ab") as f:
        f.write(b"ERROR: Did not get any data blocks\n[download] fragment not found; Skipping fragment 2 ...\n")
    with pytest.raises(fr.FragmentError):
        h.check()                                    # appeared while we fetch: stop
    log2 = _log(tmp_path / "x", "") if False else tmp_path / "other.log"
    log2.write_bytes(b"HTTP Error 403: Forbidden\n[download] Skipping fragment 5 ...\n")
    with pytest.raises(fr.FragmentError):
        fr.DownloadHealth(log2).check()              # throttled: never continue
    assert fr.DownloadHealth(tmp_path / "missing.log").check() is None
