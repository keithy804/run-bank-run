import logging
import feedparser
from config import RSS_FEEDS, NEWS_KEYWORDS

logger = logging.getLogger(__name__)


def _matches_keywords(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in NEWS_KEYWORDS)


def _source_name(feed_url: str) -> str:
    if "bbc" in feed_url:
        return "BBC Business"
    if "reuters" in feed_url:
        return "Reuters"
    if "bankofengland" in feed_url:
        return "Bank of England"
    return "News"


def fetch_news() -> list:
    items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url, agent="run-bank-run/1.0")
            source = _source_name(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "")
                if _matches_keywords(title):
                    items.append({
                        "title": title,
                        "url": entry.get("link", ""),
                        "source": source,
                        "published_at": entry.get("published", ""),
                    })
        except Exception as e:
            logger.error("news: failed to fetch %s: %s", feed_url, e)

    # Sort by published date descending (string sort works for RFC 2822 dates approximately)
    items.sort(key=lambda x: x["published_at"], reverse=True)
    return items[:10]
