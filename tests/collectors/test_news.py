from collectors.news import fetch_news

def _make_entry(title, source_url="https://bbc.co.uk/article"):
    return {
        "title": title,
        "link": source_url,
        "published": "Mon, 31 Mar 2026 06:00:00 +0000",
        "source": {"href": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    }

def _make_feed(entries):
    import types
    feed = types.SimpleNamespace()
    feed.entries = entries
    feed.bozo = False
    return feed

def test_fetch_news_filters_by_keyword(mocker):
    entries = [
        _make_entry("Bank of England raises rates"),
        _make_entry("Football results this weekend"),
        _make_entry("Barclays shares fall sharply"),
    ]
    mocker.patch("feedparser.parse", return_value=_make_feed(entries))
    result = fetch_news()
    titles = [item["title"] for item in result]
    assert "Bank of England raises rates" in titles
    assert "Barclays shares fall sharply" in titles
    assert "Football results this weekend" not in titles

def test_fetch_news_returns_at_most_10_items(mocker):
    entries = [_make_entry(f"HSBC news item {i}") for i in range(20)]
    mocker.patch("feedparser.parse", return_value=_make_feed(entries))
    result = fetch_news()
    assert len(result) <= 10

def test_fetch_news_item_has_required_fields(mocker):
    entries = [_make_entry("NatWest crisis")]
    mocker.patch("feedparser.parse", return_value=_make_feed(entries))
    mocker.patch("collectors.news.RSS_FEEDS", ["https://feeds.bbci.co.uk/news/business/rss.xml"])
    result = fetch_news()
    assert len(result) == 1
    item = result[0]
    assert "title" in item
    assert "url" in item
    assert "source" in item
    assert "published_at" in item

def test_fetch_news_continues_if_feed_fails(mocker):
    def patched_parse(url, **kwargs):
        if "bbc" in url:
            raise Exception("timeout")
        return _make_feed([_make_entry("Lloyds bank update")])

    mocker.patch("feedparser.parse", side_effect=patched_parse)
    result = fetch_news()
    assert isinstance(result, list)
