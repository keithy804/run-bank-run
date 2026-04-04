import logging
import feedparser
from config import BOE_CCYB_RATE, BOE_NEXT_FSR_DATE, BOE_NEXT_CCyB_DECISION

logger = logging.getLogger(__name__)

BOE_RSS_URL = "https://www.bankofengland.co.uk/rss/publications"

STABILITY_KEYWORDS = [
    "financial stability", "emergency", "systemic", "countercyclical",
    "capital buffer", "stress test", "financial policy committee",
]


def _is_stability_related(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in STABILITY_KEYWORDS)


def fetch_boe() -> dict:
    announcements = []
    try:
        feed = feedparser.parse(BOE_RSS_URL, agent="run-bank-run/1.0")
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            if _is_stability_related(title):
                announcements.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", ""),
                })
    except Exception as e:
        logger.error("boe: RSS fetch failed: %s", e)

    return {
        "ccyb_rate": BOE_CCYB_RATE,
        "next_fsr_date": BOE_NEXT_FSR_DATE,
        "next_ccyb_decision": BOE_NEXT_CCyB_DECISION,
        "recent_announcements": announcements[:5],
    }
