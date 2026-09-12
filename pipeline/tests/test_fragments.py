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
