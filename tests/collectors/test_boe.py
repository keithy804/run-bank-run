from collectors.boe import fetch_boe

def _make_feed(entries):
    import types
    feed = types.SimpleNamespace(entries=entries, bozo=False)
    return feed

def _make_entry(title):
    return {
        "title": title,
        "link": "https://bankofengland.co.uk/announcement",
        "published": "Mon, 31 Mar 2026 06:00:00 +0000",
    }

def test_fetch_boe_returns_expected_shape(mocker):
    mocker.patch("feedparser.parse", return_value=_make_feed([]))
    result = fetch_boe()
    assert "ccyb_rate" in result
    assert "next_fsr_date" in result
    assert "recent_announcements" in result

def test_fetch_boe_captures_stability_announcements(mocker):
    entries = [
        _make_entry("Financial Stability Report published"),
        _make_entry("Monetary Policy decision"),
        _make_entry("Emergency financial stability measures announced"),
    ]
    mocker.patch("feedparser.parse", return_value=_make_feed(entries))
    result = fetch_boe()
    titles = [a["title"] for a in result["recent_announcements"]]
    assert "Financial Stability Report published" in titles
    assert "Emergency financial stability measures announced" in titles
    # MPC-only news not captured
    assert "Monetary Policy decision" not in titles

def test_fetch_boe_handles_feed_error(mocker):
    mocker.patch("feedparser.parse", side_effect=Exception("timeout"))
    result = fetch_boe()
    assert result["recent_announcements"] == []
    assert result["ccyb_rate"] is not None
