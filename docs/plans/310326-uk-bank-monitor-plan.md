# UK Bank Stability Monitor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily-automated UK bank stability monitor with a static GitHub Pages dashboard, modular Python collectors, and Resend email alerts.

**Architecture:** Four independent Python collectors (prices, SONIA, news, BoE) feed into an orchestrator that writes `data/latest.json` and per-day history files. A static `index.html` reads the JSON via Chart.js. GitHub Actions schedules daily collection (Mon–Fri) and weekly email (Sun). Email is sent last so failures never block data collection.

**Tech Stack:** Python 3.11, yfinance, feedparser, requests, resend, pytest, pytest-mock, Chart.js (CDN), GitHub Actions, GitHub Pages

---

## Task 1: Project skeleton

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `.gitignore`
- Create: `collectors/__init__.py`
- Create: `alerts/__init__.py`
- Create: `notifier/__init__.py`
- Create: `notifier/templates/` (empty dir placeholder)
- Create: `data/history/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/collectors/__init__.py`
- Create: `tests/alerts/__init__.py`
- Create: `tests/notifier/__init__.py`

**Step 1: Create `requirements.txt`**

```
yfinance>=0.2.36
feedparser>=6.0.11
requests>=2.31.0
resend>=2.0.0
pytest>=7.4.0
pytest-mock>=3.12.0
```

**Step 2: Create `config.py`**

```python
BANKS = {
    "BARC.L": "Barclays",
    "LLOY.L": "Lloyds",
    "NWG.L": "NatWest",
    "HSBA.L": "HSBC",
}

ALERT_THRESHOLDS = {
    "price_drop_1d_pct": 5.0,
    "price_drop_5d_pct": 15.0,
    "sonia_change_1d": 0.1,
    "news_cluster_count": 3,
}

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.reuters.com/reuters/UKBusinessNews",
    "https://www.bankofengland.co.uk/rss/publications",
]

NEWS_KEYWORDS = [
    "bank", "barclays", "lloyds", "natwest", "hsbc",
    "banking", "financial stability", "bank of england",
]

# CCyB and FSR dates — update manually when BoE announces changes
BOE_CCYB_RATE = 2.0
BOE_NEXT_FSR_DATE = "Nov 2026"
BOE_NEXT_CCyB_DECISION = "Q2 2026"

# Populated from environment variables at runtime
import os
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://example.github.io/run-bank-run/")
```

**Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
.pytest_cache/
*.egg-info/
dist/
.DS_Store
```

**Step 4: Create all `__init__.py` files and directory placeholders**

```bash
touch collectors/__init__.py alerts/__init__.py notifier/__init__.py
touch tests/__init__.py tests/collectors/__init__.py tests/alerts/__init__.py tests/notifier/__init__.py
mkdir -p notifier/templates data/history
touch data/history/.gitkeep
```

**Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 6: Commit**

```bash
git add .
git commit -m "chore: project skeleton, config, and dependencies"
```

---

## Task 2: `collectors/prices.py`

**Files:**
- Create: `collectors/prices.py`
- Create: `tests/collectors/test_prices.py`

**Step 1: Write the failing tests**

```python
# tests/collectors/test_prices.py
import pandas as pd
import pytest
from collectors.prices import fetch_prices

def _make_mock_ticker(mocker, closes, high_52w=280.0, low_52w=160.0):
    dates = pd.date_range(end="2026-03-31", periods=len(closes), freq="B")
    hist = pd.DataFrame({"Close": closes}, index=dates)
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = hist
    mock_ticker.info = {"fiftyTwoWeekHigh": high_52w, "fiftyTwoWeekLow": low_52w}
    return mock_ticker

def test_fetch_prices_returns_all_banks(mocker):
    mock_ticker = _make_mock_ticker(mocker, [200.0, 205.0, 210.0])
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = fetch_prices()
    assert set(result.keys()) == {"BARC.L", "LLOY.L", "NWG.L", "HSBA.L"}

def test_fetch_prices_correct_structure(mocker):
    mock_ticker = _make_mock_ticker(mocker, [200.0, 205.0, 210.0])
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = fetch_prices()
    bank = result["BARC.L"]
    assert bank["name"] == "Barclays"
    assert bank["price"] == 210.0
    assert "change_pct_1d" in bank
    assert "change_pct_5d" in bank
    assert "change_pct_30d" in bank
    assert bank["week_52_high"] == 280.0
    assert bank["week_52_low"] == 160.0
    assert "history_90d" in bank
    assert bank["status"] in ("green", "amber", "red")

def test_fetch_prices_change_pct_1d_calculation(mocker):
    # 200 -> 210 = +5%
    mock_ticker = _make_mock_ticker(mocker, [200.0, 210.0])
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = fetch_prices()
    assert result["BARC.L"]["change_pct_1d"] == pytest.approx(5.0)

def test_fetch_prices_returns_error_on_exception(mocker):
    mocker.patch("yfinance.Ticker", side_effect=Exception("API error"))
    result = fetch_prices()
    for bank in result.values():
        assert bank["status"] == "error"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/collectors/test_prices.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`

**Step 3: Implement `collectors/prices.py`**

```python
import logging
import yfinance as yf
from config import BANKS

logger = logging.getLogger(__name__)


def _status_from_change(change_1d: float, change_5d: float) -> str:
    from config import ALERT_THRESHOLDS
    if abs(change_1d) >= ALERT_THRESHOLDS["price_drop_1d_pct"]:
        return "red"
    if abs(change_5d) >= ALERT_THRESHOLDS["price_drop_5d_pct"]:
        return "red"
    if abs(change_1d) >= ALERT_THRESHOLDS["price_drop_1d_pct"] * 0.7:
        return "amber"
    return "green"


def _pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return round((new - old) / old * 100, 2)


def fetch_prices() -> dict:
    result = {}
    for ticker_sym, name in BANKS.items():
        try:
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period="3mo")
            info = ticker.info

            if hist.empty or len(hist) < 2:
                raise ValueError("Insufficient history data")

            closes = hist["Close"].tolist()
            price = round(closes[-1], 2)
            change_1d = _pct_change(closes[-2], closes[-1])
            change_5d = _pct_change(closes[-6], closes[-1]) if len(closes) >= 6 else 0.0
            change_30d = _pct_change(closes[-31], closes[-1]) if len(closes) >= 31 else 0.0
            history_90d = [round(c, 2) for c in closes[-90:]]

            result[ticker_sym] = {
                "name": name,
                "price": price,
                "change_pct_1d": change_1d,
                "change_pct_5d": change_5d,
                "change_pct_30d": change_30d,
                "week_52_high": info.get("fiftyTwoWeekHigh", 0.0),
                "week_52_low": info.get("fiftyTwoWeekLow", 0.0),
                "history_90d": history_90d,
                "status": _status_from_change(change_1d, change_5d),
            }
        except Exception as e:
            logger.error("prices: failed to fetch %s: %s", ticker_sym, e)
            result[ticker_sym] = {
                "name": name,
                "price": None,
                "change_pct_1d": None,
                "change_pct_5d": None,
                "change_pct_30d": None,
                "week_52_high": None,
                "week_52_low": None,
                "history_90d": [],
                "status": "error",
            }
    return result
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/collectors/test_prices.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add collectors/prices.py tests/collectors/test_prices.py
git commit -m "feat: prices collector with yfinance"
```

---

## Task 3: `collectors/sonia.py`

**Files:**
- Create: `collectors/sonia.py`
- Create: `tests/collectors/test_sonia.py`

The BoE IADB API URL for SONIA (series IUDSOIA):
```
https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp?csv.x=yes&Datefrom=01/Jan/2024&Dateto=now&SeriesCodes=IUDSOIA&CSVF=TN&UsingCodes=Y
```
Response is CSV with header row `Date,IUDSOIA`, then rows like `28 Mar 2026,5.1900`.

**Step 1: Write the failing tests**

```python
# tests/collectors/test_sonia.py
import pytest
from collectors.sonia import fetch_sonia

MOCK_CSV = """Date,IUDSOIA
27 Mar 2026,5.1800
28 Mar 2026,5.1900
"""

MOCK_CSV_SINGLE_ROW = """Date,IUDSOIA
28 Mar 2026,5.1900
"""

def test_fetch_sonia_returns_correct_rate(mocker):
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=MOCK_CSV, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert result["rate"] == pytest.approx(5.19)

def test_fetch_sonia_calculates_1d_change(mocker):
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=MOCK_CSV, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert result["change_1d"] == pytest.approx(0.01)

def test_fetch_sonia_returns_history_90d(mocker):
    # Build a CSV with 95 rows
    rows = "\n".join(f"0{i % 28 + 1} Jan 2026,5.{i:04d}" for i in range(95))
    csv = f"Date,IUDSOIA\n{rows}\n"
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=csv, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert len(result["history_90d"]) == 90

def test_fetch_sonia_returns_error_on_exception(mocker):
    mocker.patch("requests.get", side_effect=Exception("timeout"))
    result = fetch_sonia()
    assert result["status"] == "error"
    assert result["rate"] is None

def test_fetch_sonia_no_1d_change_if_single_row(mocker):
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=MOCK_CSV_SINGLE_ROW, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert result["change_1d"] == 0.0
```

**Step 2: Run to verify failure**

```bash
pytest tests/collectors/test_sonia.py -v
```

**Step 3: Implement `collectors/sonia.py`**

```python
import logging
import requests
from config import ALERT_THRESHOLDS

logger = logging.getLogger(__name__)

BOE_SONIA_URL = (
    "https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"
    "?csv.x=yes&Datefrom=01/Jan/2024&Dateto=now&SeriesCodes=IUDSOIA&CSVF=TN&UsingCodes=Y"
)


def fetch_sonia() -> dict:
    try:
        resp = requests.get(BOE_SONIA_URL, timeout=30)
        resp.raise_for_status()

        rows = []
        for line in resp.text.strip().splitlines()[1:]:  # skip header
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[1].strip():
                try:
                    rows.append(float(parts[1].strip()))
                except ValueError:
                    continue

        if not rows:
            raise ValueError("No SONIA data rows parsed")

        rate = round(rows[-1], 4)
        change_1d = round(rows[-1] - rows[-2], 4) if len(rows) >= 2 else 0.0
        history_90d = [round(r, 4) for r in rows[-90:]]

        status = "green"
        if abs(change_1d) >= ALERT_THRESHOLDS["sonia_change_1d"]:
            status = "red"
        elif abs(change_1d) >= ALERT_THRESHOLDS["sonia_change_1d"] * 0.7:
            status = "amber"

        return {
            "rate": rate,
            "change_1d": change_1d,
            "history_90d": history_90d,
            "status": status,
        }
    except Exception as e:
        logger.error("sonia: fetch failed: %s", e)
        return {"rate": None, "change_1d": None, "history_90d": [], "status": "error"}
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/collectors/test_sonia.py -v
```

**Step 5: Commit**

```bash
git add collectors/sonia.py tests/collectors/test_sonia.py
git commit -m "feat: SONIA collector from BoE IADB API"
```

---

## Task 4: `collectors/news.py`

**Files:**
- Create: `collectors/news.py`
- Create: `tests/collectors/test_news.py`

**Step 1: Write the failing tests**

```python
# tests/collectors/test_news.py
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/collectors/test_news.py -v
```

**Step 3: Implement `collectors/news.py`**

```python
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
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/collectors/test_news.py -v
```

**Step 5: Commit**

```bash
git add collectors/news.py tests/collectors/test_news.py
git commit -m "feat: news collector from RSS feeds with keyword filtering"
```

---

## Task 5: `collectors/boe.py`

**Files:**
- Create: `collectors/boe.py`
- Create: `tests/collectors/test_boe.py`

This collector reads the BoE RSS feed for emergency announcements, and returns static config values for CCyB and FSR dates. CCyB/FSR values are intentionally hardcoded in `config.py` — update them manually when BoE announces changes.

**Step 1: Write the failing tests**

```python
# tests/collectors/test_boe.py
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/collectors/test_boe.py -v
```

**Step 3: Implement `collectors/boe.py`**

```python
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
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/collectors/test_boe.py -v
```

**Step 5: Commit**

```bash
git add collectors/boe.py tests/collectors/test_boe.py
git commit -m "feat: BoE collector for announcements and CCyB/FSR config"
```

---

## Task 6: `alerts/checker.py`

**Files:**
- Create: `alerts/checker.py`
- Create: `tests/alerts/test_checker.py`

**Step 1: Write the failing tests**

```python
# tests/alerts/test_checker.py
from alerts.checker import check_alerts, compute_overall_status

def _make_data(change_1d=-1.0, change_5d=-2.0, sonia_change=0.01, news_count=1):
    return {
        "prices": {
            sym: {"name": name, "change_pct_1d": change_1d, "change_pct_5d": change_5d, "status": "green"}
            for sym, name in [("BARC.L", "Barclays"), ("LLOY.L", "Lloyds"), ("NWG.L", "NatWest"), ("HSBA.L", "HSBC")]
        },
        "sonia": {"rate": 5.19, "change_1d": sonia_change, "status": "green"},
        "news": [{"title": f"Bank news {i}", "source": f"src{i}", "url": ""} for i in range(news_count)],
    }

def test_no_alerts_in_normal_conditions():
    assert check_alerts(_make_data()) == []

def test_price_drop_1d_triggers_red_alert():
    alerts = check_alerts(_make_data(change_1d=-5.1))
    assert any(a["type"] == "price_drop_1d" and a["severity"] == "red" for a in alerts)

def test_price_drop_1d_does_not_trigger_below_threshold():
    alerts = check_alerts(_make_data(change_1d=-4.9))
    assert not any(a["type"] == "price_drop_1d" for a in alerts)

def test_price_drop_5d_triggers_red_alert():
    alerts = check_alerts(_make_data(change_5d=-15.1))
    assert any(a["type"] == "price_drop_5d" and a["severity"] == "red" for a in alerts)

def test_sonia_spike_triggers_alert():
    alerts = check_alerts(_make_data(sonia_change=0.11))
    assert any(a["type"] == "sonia_spike" for a in alerts)

def test_sonia_does_not_trigger_below_threshold():
    alerts = check_alerts(_make_data(sonia_change=0.09))
    assert not any(a["type"] == "sonia_spike" for a in alerts)

def test_news_cluster_triggers_alert():
    alerts = check_alerts(_make_data(news_count=3))
    assert any(a["type"] == "news_cluster" for a in alerts)

def test_news_cluster_does_not_trigger_below_count():
    alerts = check_alerts(_make_data(news_count=2))
    assert not any(a["type"] == "news_cluster" for a in alerts)

def test_overall_status_red_when_red_alert():
    alerts = [{"severity": "red", "type": "price_drop_1d"}]
    assert compute_overall_status(alerts, {}) == "red"

def test_overall_status_amber_on_collector_error():
    alerts = []
    data = {"prices": {"BARC.L": {"status": "error"}}, "sonia": {"status": "green"}}
    assert compute_overall_status(alerts, data) == "amber"

def test_overall_status_green_when_all_clear():
    assert compute_overall_status([], {}) == "green"
```

**Step 2: Run to verify failure**

```bash
pytest tests/alerts/test_checker.py -v
```

**Step 3: Implement `alerts/checker.py`**

```python
from config import ALERT_THRESHOLDS, BANKS


def check_alerts(data: dict) -> list:
    alerts = []
    prices = data.get("prices", {})
    sonia = data.get("sonia", {})
    news = data.get("news", [])

    for sym in BANKS:
        bank = prices.get(sym, {})
        name = bank.get("name", sym)

        change_1d = bank.get("change_pct_1d")
        if change_1d is not None and change_1d <= -ALERT_THRESHOLDS["price_drop_1d_pct"]:
            alerts.append({
                "type": "price_drop_1d",
                "bank": sym,
                "severity": "red",
                "message": f"{name} dropped {abs(change_1d):.1f}% today",
            })

        change_5d = bank.get("change_pct_5d")
        if change_5d is not None and change_5d <= -ALERT_THRESHOLDS["price_drop_5d_pct"]:
            alerts.append({
                "type": "price_drop_5d",
                "bank": sym,
                "severity": "red",
                "message": f"{name} dropped {abs(change_5d):.1f}% over 5 days",
            })

    sonia_change = sonia.get("change_1d")
    if sonia_change is not None and abs(sonia_change) >= ALERT_THRESHOLDS["sonia_change_1d"]:
        alerts.append({
            "type": "sonia_spike",
            "bank": None,
            "severity": "red",
            "message": f"SONIA moved {sonia_change:+.3f}% in a single day",
        })

    if len(news) >= ALERT_THRESHOLDS["news_cluster_count"]:
        alerts.append({
            "type": "news_cluster",
            "bank": None,
            "severity": "amber",
            "message": f"{len(news)} banking-related headlines today",
        })

    return alerts


def compute_overall_status(alerts: list, data: dict) -> str:
    if any(a["severity"] == "red" for a in alerts):
        return "red"
    prices = data.get("prices", {})
    sonia = data.get("sonia", {})
    all_statuses = [v.get("status") for v in prices.values()] + [sonia.get("status")]
    if "error" in all_statuses or any(a["severity"] == "amber" for a in alerts):
        return "amber"
    return "green"
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/alerts/test_checker.py -v
```

**Step 5: Commit**

```bash
git add alerts/checker.py tests/alerts/test_checker.py
git commit -m "feat: alert checker with configurable thresholds"
```

---

## Task 7: `orchestrator.py`

**Files:**
- Create: `orchestrator.py`
- Create: `tests/test_orchestrator.py`

The orchestrator merges all collector outputs, evaluates alerts, writes JSON files, and calls the email sender. It uses `subprocess` to commit and push to git.

**Step 1: Write the failing tests**

```python
# tests/test_orchestrator.py
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from orchestrator import build_snapshot, write_json_files

def _dummy_prices():
    return {sym: {"name": n, "price": 100.0, "change_pct_1d": 0.0, "change_pct_5d": 0.0,
                  "change_pct_30d": 0.0, "week_52_high": 120.0, "week_52_low": 80.0,
                  "history_90d": [100.0], "status": "green"}
            for sym, n in [("BARC.L","Barclays"),("LLOY.L","Lloyds"),
                           ("NWG.L","NatWest"),("HSBA.L","HSBC")]}

def _dummy_sonia():
    return {"rate": 5.19, "change_1d": 0.01, "history_90d": [5.19], "status": "green"}

def test_build_snapshot_has_required_keys():
    snap = build_snapshot(
        prices=_dummy_prices(),
        sonia=_dummy_sonia(),
        news=[],
        boe={"ccyb_rate": 2.0, "next_fsr_date": "Nov 2026",
             "next_ccyb_decision": "Q2 2026", "recent_announcements": []},
    )
    for key in ("updated_at", "prices", "sonia", "news", "boe", "alerts", "overall_status"):
        assert key in snap

def test_write_json_files_creates_latest_and_history(tmp_path):
    snap = {"updated_at": "2026-03-31T07:00:00Z", "prices": {}}
    write_json_files(snap, data_dir=str(tmp_path))
    assert (tmp_path / "latest.json").exists()
    history_files = list((tmp_path / "history").glob("*.json"))
    assert len(history_files) == 1

def test_write_json_files_latest_is_valid_json(tmp_path):
    snap = {"updated_at": "2026-03-31T07:00:00Z"}
    write_json_files(snap, data_dir=str(tmp_path))
    with open(tmp_path / "latest.json") as f:
        loaded = json.load(f)
    assert loaded["updated_at"] == "2026-03-31T07:00:00Z"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_orchestrator.py -v
```

**Step 3: Implement `orchestrator.py`**

```python
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

from collectors.prices import fetch_prices
from collectors.sonia import fetch_sonia
from collectors.news import fetch_news
from collectors.boe import fetch_boe
from alerts.checker import check_alerts, compute_overall_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def build_snapshot(prices: dict, sonia: dict, news: list, boe: dict) -> dict:
    data = {"prices": prices, "sonia": sonia, "news": news, "boe": boe}
    alerts = check_alerts(data)
    overall_status = compute_overall_status(alerts, data)
    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prices": prices,
        "sonia": sonia,
        "news": news,
        "boe": boe,
        "alerts": alerts,
        "overall_status": overall_status,
    }


def write_json_files(snapshot: dict, data_dir: str = DATA_DIR) -> None:
    os.makedirs(data_dir, exist_ok=True)
    history_dir = os.path.join(data_dir, "history")
    os.makedirs(history_dir, exist_ok=True)

    latest_path = os.path.join(data_dir, "latest.json")
    with open(latest_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    logger.info("Wrote %s", latest_path)

    date_str = datetime.now().strftime("%d%m%y")
    history_path = os.path.join(history_dir, f"{date_str}.json")
    # History file: minimal snapshot (no history arrays — keeps files small)
    history_snap = {
        "date": date_str,
        "updated_at": snapshot["updated_at"],
        "prices": {sym: {k: v for k, v in bank.items() if k != "history_90d"}
                   for sym, bank in snapshot["prices"].items()},
        "sonia": {k: v for k, v in snapshot["sonia"].items() if k != "history_90d"},
        "alerts": snapshot["alerts"],
        "overall_status": snapshot["overall_status"],
    }
    with open(history_path, "w") as f:
        json.dump(history_snap, f, indent=2)
    logger.info("Wrote %s", history_path)


def commit_and_push() -> None:
    try:
        subprocess.run(
            ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
            check=True
        )
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "add", "data/"], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"data: update {datetime.now().strftime('%d/%m/%y')}"],
            check=True
        )
        subprocess.run(["git", "push"], check=True)
        logger.info("Git commit and push successful")
    except subprocess.CalledProcessError as e:
        # Retry once
        logger.warning("Git push failed, retrying: %s", e)
        subprocess.run(["git", "push"], check=True)


def run(send_email: bool = True) -> None:
    logger.info("=== Starting data collection ===")

    logger.info("Fetching prices...")
    prices = fetch_prices()

    logger.info("Fetching SONIA...")
    sonia = fetch_sonia()

    logger.info("Fetching news...")
    news = fetch_news()

    logger.info("Fetching BoE data...")
    boe = fetch_boe()

    snapshot = build_snapshot(prices, sonia, news, boe)
    logger.info("Overall status: %s, Alerts: %d", snapshot["overall_status"], len(snapshot["alerts"]))

    write_json_files(snapshot)

    commit_and_push()

    if send_email:
        from notifier.daily import send_daily_email
        try:
            send_daily_email(snapshot)
            logger.info("Daily email sent")
        except Exception as e:
            logger.error("Daily email failed (non-blocking): %s", e)

    logger.info("=== Collection complete ===")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run(send_email=not dry_run)
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_orchestrator.py -v
```

**Step 5: Run all tests**

```bash
pytest -v
```

Expected: all PASS

**Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator — collect, merge, write JSON, commit"
```

---

## Task 8: `notifier/daily.py` + HTML template

**Files:**
- Create: `notifier/daily.py`
- Create: `notifier/templates/daily.html`
- Create: `tests/notifier/test_daily.py`

**Step 1: Write the failing tests**

```python
# tests/notifier/test_daily.py
from notifier.daily import build_daily_html, build_subject

def _snapshot(overall_status="green", alerts=None, change_1d=0.5):
    return {
        "updated_at": "2026-03-31T07:00:00Z",
        "overall_status": overall_status,
        "alerts": alerts or [],
        "prices": {
            sym: {"name": name, "price": 100.0, "change_pct_1d": change_1d, "status": "green"}
            for sym, name in [("BARC.L","Barclays"),("LLOY.L","Lloyds"),
                               ("NWG.L","NatWest"),("HSBA.L","HSBC")]
        },
        "sonia": {"rate": 5.19, "change_1d": 0.01, "status": "green"},
        "news": [
            {"title": "Bank news", "source": "BBC", "url": "https://bbc.co.uk/1"},
            {"title": "More news", "source": "Reuters", "url": "https://reuters.com/1"},
        ],
        "boe": {"ccyb_rate": 2.0, "next_fsr_date": "Nov 2026",
                "next_ccyb_decision": "Q2 2026", "recent_announcements": []},
    }

def test_subject_all_clear():
    assert "All Clear" in build_subject(_snapshot())
    assert "✅" in build_subject(_snapshot())

def test_subject_with_alert():
    snap = _snapshot(overall_status="red", alerts=[{"severity": "red", "message": "Barclays dropped"}])
    subj = build_subject(snap)
    assert "⚠" in subj

def test_html_contains_bank_names():
    html = build_daily_html(_snapshot())
    for name in ["Barclays", "Lloyds", "NatWest", "HSBC"]:
        assert name in html

def test_html_contains_sonia():
    assert "5.19" in build_daily_html(_snapshot())

def test_html_contains_headlines():
    assert "Bank news" in build_daily_html(_snapshot())

def test_html_contains_alert_when_present():
    snap = _snapshot(alerts=[{"severity": "red", "message": "Barclays dropped 6%", "type": "price_drop_1d"}])
    html = build_daily_html(snap)
    assert "Barclays dropped 6%" in html
```

**Step 2: Run to verify failure**

```bash
pytest tests/notifier/test_daily.py -v
```

**Step 3: Create `notifier/templates/daily.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.6;
         color: #1a1a1a; background: #ffffff; margin: 0; padding: 0; }
  .wrap { max-width: 600px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .ts { font-size: 13px; color: #666; margin-bottom: 20px; }
  .alerts { background: #c0392b; color: #fff; padding: 12px 16px;
            border-radius: 6px; margin-bottom: 20px; font-weight: bold; }
  .alerts ul { margin: 8px 0 0; padding-left: 20px; }
  h2 { font-size: 17px; border-bottom: 2px solid #eee; padding-bottom: 4px; margin-top: 24px; }
  .banks { width: 100%; border-collapse: collapse; }
  .banks td { padding: 8px 6px; font-size: 15px; }
  .banks tr:nth-child(even) { background: #f7f7f7; }
  .green { color: #1a7a1a; font-weight: bold; }
  .amber { color: #b36200; font-weight: bold; }
  .red   { color: #c0392b; font-weight: bold; }
  .error { color: #888; }
  .headlines li { margin-bottom: 8px; }
  .headlines a { color: #1a56a0; text-decoration: none; }
  .source { font-size: 12px; color: #888; margin-left: 6px; }
  .footer { margin-top: 28px; font-size: 13px; color: #888; }
  .cta { display: inline-block; margin-top: 16px; padding: 10px 20px;
         background: #1a56a0; color: #fff; text-decoration: none;
         border-radius: 4px; font-size: 15px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>UK Bank Stability Monitor</h1>
  <p class="ts">{{updated_display}}</p>

  {{#alerts}}
  <div class="alerts">
    ⚠ Alert{{#plural}}s{{/plural}} today:
    <ul>
      {{#alert_list}}<li>{{message}}</li>{{/alert_list}}
    </ul>
  </div>
  {{/alerts}}

  <h2>Share Prices</h2>
  <table class="banks">
    {{#banks}}
    <tr>
      <td>{{status_symbol}} <strong>{{name}}</strong></td>
      <td>{{price}}p</td>
      <td class="{{status_class}}">{{direction}}{{change_pct_1d}}%</td>
    </tr>
    {{/banks}}
  </table>

  <h2>SONIA Rate</h2>
  <p>{{sonia_rate}}% &nbsp;<span class="{{sonia_status_class}}">{{sonia_direction}}{{sonia_change}} today</span></p>

  <h2>Headlines</h2>
  <ul class="headlines">
    {{#news}}<li><a href="{{url}}">{{title}}</a><span class="source">{{source}}</span></li>{{/news}}
  </ul>

  <a class="cta" href="{{dashboard_url}}">Open Dashboard</a>

  <p class="footer">Run Bank Run — automated monitor</p>
</div>
</body>
</html>
```

**Step 4: Implement `notifier/daily.py`**

```python
import logging
import os
import resend
from datetime import datetime, timezone
from config import RESEND_API_KEY, EMAIL_TO, DASHBOARD_URL

logger = logging.getLogger(__name__)

STATUS_SYMBOL = {"green": "🟢", "amber": "🟡", "red": "🔴", "error": "⚪"}
STATUS_CLASS  = {"green": "green", "amber": "amber", "red": "red", "error": "error"}


def build_subject(snapshot: dict) -> str:
    dt = datetime.now()
    date_str = dt.strftime("%d/%m/%y")
    alerts = snapshot.get("alerts", [])
    if alerts:
        count = len(alerts)
        return f"Bank Monitor — {date_str} ⚠ {count} Alert{'s' if count > 1 else ''}"
    return f"Bank Monitor — {date_str} ✅ All Clear"


def build_daily_html(snapshot: dict) -> str:
    tmpl_path = os.path.join(os.path.dirname(__file__), "templates", "daily.html")
    with open(tmpl_path) as f:
        tmpl = f.read()

    alerts = snapshot.get("alerts", [])
    prices = snapshot.get("prices", {})
    sonia  = snapshot.get("sonia", {})
    news   = snapshot.get("news", [])[:3]

    # Build bank rows
    bank_rows = ""
    for sym, bank in prices.items():
        status = bank.get("status", "error")
        change = bank.get("change_pct_1d") or 0.0
        direction = "▼ " if change < 0 else "▲ "
        price = bank.get("price")
        price_str = f"{price:.2f}" if price is not None else "N/A"
        bank_rows += (
            f"<tr><td>{STATUS_SYMBOL.get(status,'⚪')} <strong>{bank['name']}</strong></td>"
            f"<td>{price_str}p</td>"
            f"<td class=\"{STATUS_CLASS.get(status,'error')}\">{direction}{abs(change):.2f}%</td></tr>\n"
        )

    # Build headline rows
    news_rows = "".join(
        f'<li><a href="{item["url"]}">{item["title"]}</a>'
        f'<span class="source">{item["source"]}</span></li>'
        for item in news
    )

    # Alerts block
    alert_block = ""
    if alerts:
        items = "".join(f"<li>{a['message']}</li>" for a in alerts)
        plural = "s" if len(alerts) > 1 else ""
        alert_block = (
            f'<div class="alerts">⚠ Alert{plural} today:<ul>{items}</ul></div>'
        )

    sonia_rate   = sonia.get("rate") or "N/A"
    sonia_change = sonia.get("change_1d") or 0.0
    sonia_dir    = "▼ " if sonia_change < 0 else "▲ "
    sonia_cls    = STATUS_CLASS.get(sonia.get("status", "green"), "green")
    dt_display   = datetime.now().strftime("%d/%m/%y %H:%M UTC")

    html = (
        tmpl
        .replace("{{updated_display}}", dt_display)
        .replace("{{#alerts}}{{/alerts}}", "")
        .replace("{{#alerts}}\n  <div class", alert_block + "\n  <!--div class" if not alerts else "  <div class")
        .replace("{{banks}}", bank_rows)
        .replace("{{news}}", news_rows)
        .replace("{{sonia_rate}}", str(sonia_rate))
        .replace("{{sonia_direction}}", sonia_dir)
        .replace("{{sonia_change}}", f"{abs(sonia_change):.3f}")
        .replace("{{sonia_status_class}}", sonia_cls)
        .replace("{{dashboard_url}}", DASHBOARD_URL)
    )

    # Simple template cleanup — remove unfilled mustache tags
    import re
    html = re.sub(r"\{\{[^}]+\}\}", "", html)
    html = re.sub(r"\{\{#[^}]+\}\}.*?\{\{/[^}]+\}\}", "", html, flags=re.DOTALL)
    return html


def send_daily_email(snapshot: dict) -> None:
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY not set")
    if not EMAIL_TO:
        raise ValueError("EMAIL_TO not set")

    resend.api_key = RESEND_API_KEY
    resend.Emails.send({
        "from": "Bank Monitor <monitor@updates.run-bank-run.com>",
        "to": EMAIL_TO,
        "subject": build_subject(snapshot),
        "html": build_daily_html(snapshot),
    })
```

**Step 5: Run tests to verify pass**

```bash
pytest tests/notifier/test_daily.py -v
```

**Step 6: Commit**

```bash
git add notifier/daily.py notifier/templates/daily.html tests/notifier/test_daily.py
git commit -m "feat: daily email builder and HTML template"
```

---

## Task 9: `notifier/weekly.py` + HTML template

**Files:**
- Create: `notifier/weekly.py`
- Create: `notifier/templates/weekly.html`
- Create: `tests/notifier/test_weekly.py`
- Create: `send_weekly_email.py`

**Step 1: Write the failing tests**

```python
# tests/notifier/test_weekly.py
from notifier.weekly import build_weekly_html, build_subject, plain_english_summary

def _weekly_data():
    return {
        "snapshot": {
            "updated_at": "2026-03-31T07:00:00Z",
            "prices": {
                sym: {"name": name, "price": 100.0, "change_pct_1d": -1.0, "status": "green"}
                for sym, name in [("BARC.L","Barclays"),("LLOY.L","Lloyds"),
                                   ("NWG.L","NatWest"),("HSBA.L","HSBC")]
            },
            "sonia": {"rate": 5.19, "change_1d": 0.0, "status": "green"},
            "boe": {"ccyb_rate": 2.0, "next_fsr_date": "Nov 2026",
                    "next_ccyb_decision": "Q2 2026", "recent_announcements": []},
            "alerts": [],
            "overall_status": "green",
        },
        "week_alerts": [],
        "week_price_changes": {
            "BARC.L": -2.1, "LLOY.L": 0.3, "NWG.L": -0.8, "HSBA.L": -1.2
        },
        "sonia_week_avg": 5.19,
    }

def test_subject_format():
    assert "Week of" in build_subject()
    assert "📊" in build_subject()

def test_html_contains_bank_names():
    html = build_weekly_html(_weekly_data())
    for name in ["Barclays", "Lloyds", "NatWest", "HSBC"]:
        assert name in html

def test_html_contains_week_changes():
    html = build_weekly_html(_weekly_data())
    assert "2.1%" in html

def test_plain_english_quiet_week():
    summary = plain_english_summary([], {"BARC.L": -0.5, "LLOY.L": 0.2})
    assert "quiet" in summary.lower()

def test_plain_english_active_week():
    alerts = [{"severity": "red", "message": "Barclays dropped"}]
    summary = plain_english_summary(alerts, {"BARC.L": -6.0})
    assert "alert" in summary.lower()
```

**Step 2: Run to verify failure**

```bash
pytest tests/notifier/test_weekly.py -v
```

**Step 3: Create `notifier/templates/weekly.html`**

Keep the same CSS as `daily.html` (copy the `<style>` block), then:

```html
<!-- body content only — wrap in same boilerplate as daily.html -->
<h1>UK Bank Monitor — Weekly Summary</h1>
<p class="ts">Week of {{week_start}} &nbsp;·&nbsp; {{updated_display}}</p>

{{alert_block}}

<h2>Week-over-Week Price Changes</h2>
<table class="banks">{{week_price_rows}}</table>

<h2>SONIA</h2>
<p>Weekly average: <strong>{{sonia_avg}}%</strong></p>

<h2>Alerts This Week</h2>
<p>{{week_alerts_summary}}</p>

<h2>Upcoming BoE Events</h2>
<ul>
  <li>Financial Stability Report: {{next_fsr_date}}</li>
  <li>CCyB decision: {{next_ccyb_decision}}</li>
</ul>

<h2>Summary</h2>
<p>{{plain_english}}</p>

<a class="cta" href="{{dashboard_url}}">Open Dashboard</a>
```

**Step 4: Implement `notifier/weekly.py`**

```python
import json
import logging
import os
import re
import resend
from datetime import datetime, timedelta
from config import RESEND_API_KEY, EMAIL_TO, DASHBOARD_URL, BANKS

logger = logging.getLogger(__name__)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_latest_snapshot() -> dict:
    with open(os.path.join(DATA_DIR, "latest.json")) as f:
        return json.load(f)


def load_history_snapshot(days_ago: int) -> dict | None:
    date = (datetime.now() - timedelta(days=days_ago)).strftime("%d%m%y")
    path = os.path.join(DATA_DIR, "history", f"{date}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def compute_week_changes(current: dict, week_ago: dict | None) -> dict:
    changes = {}
    for sym in BANKS:
        curr_price = current.get("prices", {}).get(sym, {}).get("price")
        prev_price = week_ago.get("prices", {}).get(sym, {}).get("price") if week_ago else None
        if curr_price and prev_price:
            changes[sym] = round((curr_price - prev_price) / prev_price * 100, 2)
        else:
            changes[sym] = None
    return changes


def plain_english_summary(week_alerts: list, week_changes: dict) -> str:
    if week_alerts:
        n = len(week_alerts)
        return (
            f"An active week. {n} alert{'s' if n > 1 else ''} triggered. "
            "Check the dashboard for details."
        )
    big_moves = {sym: ch for sym, ch in week_changes.items()
                 if ch is not None and abs(ch) >= 3.0}
    if big_moves:
        details = ", ".join(
            f"{BANKS[sym]} {ch:+.1f}%" for sym, ch in big_moves.items()
        )
        return f"A notable week. Larger moves: {details}. No thresholds breached."
    return "A quiet week. All banks within normal ranges. No thresholds breached."


def build_subject() -> str:
    week_start = (datetime.now() - timedelta(days=6)).strftime("%d/%m/%y")
    return f"Bank Monitor — Week of {week_start} 📊"


def build_weekly_html(data: dict) -> str:
    tmpl_path = os.path.join(os.path.dirname(__file__), "templates", "weekly.html")
    with open(tmpl_path) as f:
        tmpl = f.read()

    snap          = data["snapshot"]
    week_alerts   = data["week_alerts"]
    week_changes  = data["week_price_changes"]
    sonia_avg     = data["sonia_week_avg"]

    STATUS_SYMBOL = {"green": "🟢", "amber": "🟡", "red": "🔴", "error": "⚪"}

    price_rows = ""
    for sym, change in week_changes.items():
        name = BANKS[sym]
        status = snap["prices"].get(sym, {}).get("status", "error")
        change_str = f"{change:+.1f}%" if change is not None else "N/A"
        cls = "green" if (change or 0) > 0 else ("red" if (change or 0) < -3 else "amber")
        price_rows += (
            f"<tr><td>{STATUS_SYMBOL.get(status,'⚪')} <strong>{name}</strong></td>"
            f"<td class=\"{cls}\">{change_str} this week</td></tr>\n"
        )

    alert_block = ""
    if week_alerts:
        items = "".join(f"<li>{a['message']}</li>" for a in week_alerts)
        alert_block = f'<div class="alerts">⚠ {len(week_alerts)} alerts this week:<ul>{items}</ul></div>'

    alerts_summary = (
        f"{len(week_alerts)} alert{'s' if len(week_alerts) > 1 else ''} triggered."
        if week_alerts else "None."
    )

    boe = snap.get("boe", {})
    html = (
        tmpl
        .replace("{{week_start}}", (datetime.now() - timedelta(days=6)).strftime("%d/%m/%y"))
        .replace("{{updated_display}}", datetime.now().strftime("%d/%m/%y %H:%M UTC"))
        .replace("{{alert_block}}", alert_block)
        .replace("{{week_price_rows}}", price_rows)
        .replace("{{sonia_avg}}", str(sonia_avg))
        .replace("{{week_alerts_summary}}", alerts_summary)
        .replace("{{next_fsr_date}}", boe.get("next_fsr_date", "TBC"))
        .replace("{{next_ccyb_decision}}", boe.get("next_ccyb_decision", "TBC"))
        .replace("{{plain_english}}", plain_english_summary(week_alerts, week_changes))
        .replace("{{dashboard_url}}", DASHBOARD_URL)
    )
    html = re.sub(r"\{\{[^}]+\}\}", "", html)
    return html


def send_weekly_email() -> None:
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY not set")
    if not EMAIL_TO:
        raise ValueError("EMAIL_TO not set")

    snapshot  = load_latest_snapshot()
    week_ago  = load_history_snapshot(7)
    week_changes = compute_week_changes(snapshot, week_ago)

    # Collect all alerts from the week's history files
    week_alerts = []
    for days_ago in range(1, 8):
        h = load_history_snapshot(days_ago)
        if h:
            week_alerts.extend(h.get("alerts", []))

    data = {
        "snapshot": snapshot,
        "week_alerts": week_alerts,
        "week_price_changes": week_changes,
        "sonia_week_avg": snapshot["sonia"].get("rate"),
    }

    resend.api_key = RESEND_API_KEY
    resend.Emails.send({
        "from": "Bank Monitor <monitor@updates.run-bank-run.com>",
        "to": EMAIL_TO,
        "subject": build_subject(),
        "html": build_weekly_html(data),
    })
    logger.info("Weekly email sent")
```

**Step 5: Create `send_weekly_email.py`** (entry point for the weekly workflow)

```python
import logging
from notifier.weekly import send_weekly_email

logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    send_weekly_email()
```

**Step 6: Run tests to verify pass**

```bash
pytest tests/notifier/test_weekly.py -v
```

**Step 7: Run all tests**

```bash
pytest -v
```

Expected: all PASS

**Step 8: Commit**

```bash
git add notifier/weekly.py notifier/templates/weekly.html tests/notifier/test_weekly.py send_weekly_email.py
git commit -m "feat: weekly email builder and HTML template"
```

---

## Task 10: `index.html` — static dashboard

**Files:**
- Create: `index.html`

No unit tests for this task. Verify by opening in a browser after running the orchestrator.

**Step 1: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UK Bank Stability Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --green: #1a7a1a; --amber: #b36200; --red: #c0392b; --error: #888;
    --bg: #f5f5f5; --card-bg: #fff; --text: #1a1a1a; --muted: #666;
    --border: #ddd;
  }
  * { box-sizing: border-box; }
  body { font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.6;
         background: var(--bg); color: var(--text); margin: 0; padding: 0; }
  header { background: #1a2740; color: #fff; padding: 16px 20px; }
  header h1 { margin: 0; font-size: 20px; }
  header p  { margin: 2px 0 0; font-size: 13px; opacity: 0.8; }
  .stale-warning { background: #b36200; color: #fff; text-align: center;
                   padding: 10px; font-weight: bold; display: none; }
  #alert-banner { background: var(--red); color: #fff; padding: 12px 20px;
                  font-size: 15px; font-weight: bold; display: none; }
  #alert-banner ul { margin: 6px 0 0; padding-left: 20px; }
  main { max-width: 900px; margin: 0 auto; padding: 20px 16px; }
  section { background: var(--card-bg); border: 1px solid var(--border);
            border-radius: 8px; padding: 20px; margin-bottom: 20px; }
  h2 { font-size: 17px; margin: 0 0 14px; padding-bottom: 6px;
       border-bottom: 2px solid var(--border); }
  .bank-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  @media (min-width: 640px) { .bank-grid { grid-template-columns: repeat(4, 1fr); } }
  .bank-card { border: 2px solid var(--border); border-radius: 8px; padding: 14px 12px; }
  .bank-card.green { border-color: var(--green); }
  .bank-card.amber { border-color: var(--amber); }
  .bank-card.red   { border-color: var(--red); }
  .bank-card .name { font-weight: bold; font-size: 15px; }
  .bank-card .price { font-size: 22px; font-weight: bold; margin: 4px 0; }
  .bank-card .change { font-size: 14px; }
  .bank-card .change.up   { color: var(--green); }
  .bank-card .change.down { color: var(--red); }
  .bank-card .status-icon { font-size: 18px; float: right; }
  .toggle-group { margin-bottom: 12px; }
  .toggle-group button { padding: 5px 12px; margin-right: 6px; border: 1px solid var(--border);
                         background: #fff; border-radius: 4px; cursor: pointer; font-size: 14px; }
  .toggle-group button.active { background: #1a2740; color: #fff; border-color: #1a2740; }
  canvas { max-height: 260px; }
  .headlines li { margin-bottom: 10px; }
  .headlines a { color: #1a56a0; text-decoration: none; font-size: 15px; }
  .headlines a:hover { text-decoration: underline; }
  .source-tag { font-size: 12px; color: var(--muted); margin-left: 6px;
                background: #eee; padding: 1px 6px; border-radius: 10px; }
  .boe-footer { font-size: 14px; color: var(--muted); }
  footer { text-align: center; font-size: 12px; color: var(--muted); padding: 20px; }
</style>
</head>
<body>

<header>
  <h1>🏦 UK Bank Stability Monitor</h1>
  <p id="last-updated">Loading...</p>
</header>

<div class="stale-warning" id="stale-warning">
  ⚠ Data may be stale — last update was over 48 hours ago
</div>

<div id="alert-banner"></div>

<main>
  <!-- Bank status cards -->
  <section>
    <h2>Bank Status</h2>
    <div class="bank-grid" id="bank-cards">Loading...</div>
  </section>

  <!-- Share price chart -->
  <section>
    <h2>Share Prices</h2>
    <div class="toggle-group">
      <button class="active" onclick="setRange('prices', 7, this)">7d</button>
      <button onclick="setRange('prices', 30, this)">30d</button>
      <button onclick="setRange('prices', 90, this)">90d</button>
    </div>
    <canvas id="prices-chart"></canvas>
  </section>

  <!-- SONIA chart -->
  <section>
    <h2>SONIA Rate</h2>
    <canvas id="sonia-chart"></canvas>
  </section>

  <!-- Headlines -->
  <section>
    <h2>Latest Headlines</h2>
    <ul class="headlines" id="headlines">Loading...</ul>
  </section>

  <!-- BoE footer -->
  <section>
    <h2>Bank of England</h2>
    <div class="boe-footer" id="boe-info">Loading...</div>
  </section>
</main>

<footer>Run Bank Run — personal monitor · Data from Yahoo Finance, BoE, RSS</footer>

<script>
const BANK_COLOURS = {
  "BARC.L": "#1f77b4", "LLOY.L": "#ff7f0e",
  "NWG.L":  "#2ca02c", "HSBA.L": "#d62728"
};
const STATUS_ICON = { green: "🟢", amber: "🟡", red: "🔴", error: "⚪" };

let data = null;
let pricesChart = null;
let soniaChart = null;

async function loadData() {
  const resp = await fetch("data/latest.json?_=" + Date.now());
  data = await resp.json();
  render();
}

function render() {
  renderHeader();
  renderAlertBanner();
  renderBankCards();
  renderPricesChart(30);
  renderSoniaChart();
  renderHeadlines();
  renderBoE();
}

function renderHeader() {
  const dt = new Date(data.updated_at);
  const dd = String(dt.getUTCDate()).padStart(2,'0');
  const mm = String(dt.getUTCMonth()+1).padStart(2,'0');
  const yy = String(dt.getUTCFullYear()).slice(-2);
  const hh = String(dt.getUTCHours()).padStart(2,'0');
  const mn = String(dt.getUTCMinutes()).padStart(2,'0');
  document.getElementById("last-updated").textContent =
    `Last updated: ${dd}/${mm}/${yy} ${hh}:${mn} UTC`;

  const ageHours = (Date.now() - dt.getTime()) / 3600000;
  if (ageHours > 48) {
    document.getElementById("stale-warning").style.display = "block";
  }
}

function renderAlertBanner() {
  const alerts = data.alerts || [];
  const banner = document.getElementById("alert-banner");
  if (!alerts.length) return;
  banner.style.display = "block";
  banner.innerHTML = `⚠ ${alerts.length} Alert${alerts.length > 1 ? 's' : ''}<ul>`
    + alerts.map(a => `<li>${a.message}</li>`).join("") + "</ul>";
}

function renderBankCards() {
  const container = document.getElementById("bank-cards");
  container.innerHTML = "";
  for (const [sym, bank] of Object.entries(data.prices)) {
    const status = bank.status || "error";
    const change = bank.change_pct_1d ?? 0;
    const dir = change >= 0 ? "▲" : "▼";
    const dirClass = change >= 0 ? "up" : "down";
    const price = bank.price != null ? bank.price.toFixed(2) + "p" : "N/A";
    container.innerHTML += `
      <div class="bank-card ${status}">
        <span class="status-icon">${STATUS_ICON[status] || "⚪"}</span>
        <div class="name">${bank.name}</div>
        <div class="price">${price}</div>
        <div class="change ${dirClass}">${dir} ${Math.abs(change).toFixed(2)}% today</div>
      </div>`;
  }
}

function setRange(type, days, btn) {
  document.querySelectorAll(`.toggle-group button`).forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  if (type === "prices") renderPricesChart(days);
}

function renderPricesChart(days) {
  const ctx = document.getElementById("prices-chart");
  if (pricesChart) pricesChart.destroy();
  const datasets = Object.entries(data.prices).map(([sym, bank]) => {
    const hist = (bank.history_90d || []).slice(-days);
    return { label: bank.name, data: hist, borderColor: BANK_COLOURS[sym],
             backgroundColor: "transparent", borderWidth: 2, pointRadius: 0, tension: 0.3 };
  });
  const labels = datasets[0]?.data.map((_, i) => `-${datasets[0].data.length - 1 - i}d`) || [];
  pricesChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: { title: { display: true, text: "Price (p)" } },
        x: { ticks: { maxTicksLimit: 8 } }
      }
    }
  });
}

function renderSoniaChart() {
  const ctx = document.getElementById("sonia-chart");
  if (soniaChart) soniaChart.destroy();
  const hist = data.sonia?.history_90d?.slice(-30) || [];
  const labels = hist.map((_, i) => `-${hist.length - 1 - i}d`);
  soniaChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{ label: "SONIA %", data: hist, borderColor: "#1a2740",
                   backgroundColor: "rgba(26,39,64,0.08)", borderWidth: 2,
                   pointRadius: 0, tension: 0.3, fill: true }]
    },
    options: {
      animation: false,
      scales: {
        y: { title: { display: true, text: "Rate (%)" } },
        x: { ticks: { maxTicksLimit: 8 } }
      }
    }
  });
}

function renderHeadlines() {
  const list = document.getElementById("headlines");
  const news = data.news || [];
  if (!news.length) { list.innerHTML = "<li>No recent headlines found.</li>"; return; }
  list.innerHTML = news.map(item =>
    `<li><a href="${item.url}" target="_blank" rel="noopener">${item.title}</a>
     <span class="source-tag">${item.source}</span></li>`
  ).join("");
}

function renderBoE() {
  const boe = data.boe || {};
  const el = document.getElementById("boe-info");
  el.innerHTML = `
    <p><strong>CCyB Rate:</strong> ${boe.ccyb_rate ?? "N/A"}%
       &nbsp;·&nbsp; <strong>Next FSR:</strong> ${boe.next_fsr_date ?? "TBC"}
       &nbsp;·&nbsp; <strong>CCyB Decision:</strong> ${boe.next_ccyb_decision ?? "TBC"}</p>
    ${(boe.recent_announcements || []).length ?
      "<p><strong>Recent BoE Announcements:</strong></p><ul>" +
      boe.recent_announcements.map(a =>
        `<li><a href="${a.url}" target="_blank">${a.title}</a></li>`
      ).join("") + "</ul>" : ""}
  `;
}

loadData().catch(err => {
  document.getElementById("last-updated").textContent = "Failed to load data";
  console.error(err);
});
</script>
</body>
</html>
```

**Step 2: Create a minimal `data/latest.json` for local testing**

```bash
python orchestrator.py --dry-run
```

If that fails (no real data yet), create a minimal stub:

```bash
mkdir -p data/history
```

```json
{
  "updated_at": "2026-03-31T07:00:00Z",
  "prices": {
    "BARC.L": {"name":"Barclays","price":210.5,"change_pct_1d":-0.8,"change_pct_5d":-2.1,"change_pct_30d":5.3,"week_52_high":280.0,"week_52_low":160.0,"history_90d":[208,209,210.5],"status":"green"},
    "LLOY.L": {"name":"Lloyds","price":55.2,"change_pct_1d":0.2,"change_pct_5d":0.8,"change_pct_30d":3.1,"week_52_high":65.0,"week_52_low":42.0,"history_90d":[54.8,55.0,55.2],"status":"green"},
    "NWG.L":  {"name":"NatWest","price":380.0,"change_pct_1d":-0.1,"change_pct_5d":-1.2,"change_pct_30d":4.2,"week_52_high":420.0,"week_52_low":280.0,"history_90d":[381,380.5,380.0],"status":"green"},
    "HSBA.L": {"name":"HSBC","price":720.0,"change_pct_1d":-4.9,"change_pct_5d":-8.0,"change_pct_30d":-2.0,"week_52_high":810.0,"week_52_low":580.0,"history_90d":[750,735,720.0],"status":"amber"}
  },
  "sonia": {"rate":5.19,"change_1d":0.01,"history_90d":[5.18,5.185,5.19],"status":"green"},
  "news": [
    {"title":"Bank of England holds rates steady","source":"BBC Business","url":"https://bbc.co.uk/","published_at":"Mon, 31 Mar 2026 06:00:00 +0000"},
    {"title":"HSBC shares under pressure amid global concerns","source":"Reuters","url":"https://reuters.com/","published_at":"Mon, 31 Mar 2026 05:30:00 +0000"}
  ],
  "boe": {"ccyb_rate":2.0,"next_fsr_date":"Nov 2026","next_ccyb_decision":"Q2 2026","recent_announcements":[]},
  "alerts": [],
  "overall_status": "green"
}
```

**Step 3: Open dashboard in browser**

```bash
open index.html
```

Verify: bank cards visible, charts render, headlines show, no JS console errors.

**Step 4: Commit**

```bash
git add index.html data/latest.json data/history/.gitkeep
git commit -m "feat: static dashboard with Chart.js"
```

---

## Task 11: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/daily.yml`
- Create: `.github/workflows/weekly.yml`

No unit tests. Verify by pushing to GitHub and watching Actions run.

**Step 1: Create `.github/workflows/daily.yml`**

```yaml
name: Daily data collection

on:
  schedule:
    - cron: "0 7 * * 1-5"   # 7am UTC Mon–Fri
  workflow_dispatch:          # Allow manual trigger

permissions:
  contents: write

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run data collection
        env:
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          DASHBOARD_URL: ${{ secrets.DASHBOARD_URL }}
        run: python orchestrator.py
```

**Step 2: Create `.github/workflows/weekly.yml`**

```yaml
name: Weekly summary email

on:
  schedule:
    - cron: "0 7 * * 0"     # 7am UTC Sunday
  workflow_dispatch:

jobs:
  weekly-email:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Send weekly email
        env:
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          DASHBOARD_URL: ${{ secrets.DASHBOARD_URL }}
        run: python send_weekly_email.py
```

**Step 3: Commit**

```bash
git add .github/
git commit -m "feat: GitHub Actions workflows for daily collection and weekly email"
```

---

## Task 12: Deploy to GitHub and configure GitHub Pages

**Step 1: Create a GitHub repo named `run-bank-run`**

Go to github.com → New repository → name: `run-bank-run` → Public → no README (repo already has files).

**Step 2: Push the repo**

```bash
git remote add origin https://github.com/<YOUR_USERNAME>/run-bank-run.git
git branch -M main
git push -u origin main
```

**Step 3: Enable GitHub Pages**

In repo Settings → Pages → Source: Deploy from a branch → Branch: main → Folder: / (root) → Save.

After a minute, the dashboard will be live at `https://<YOUR_USERNAME>.github.io/run-bank-run/`.

**Step 4: Add GitHub Actions secrets**

In repo Settings → Secrets and variables → Actions → New repository secret:

| Name | Value |
|---|---|
| `RESEND_API_KEY` | Your Resend API key |
| `EMAIL_TO` | Your email address |
| `DASHBOARD_URL` | `https://<YOUR_USERNAME>.github.io/run-bank-run/` |

**Step 5: Update `config.py` DASHBOARD_URL default** (optional — it'll be overridden by the env var anyway)

**Step 6: Trigger a manual run**

In the GitHub Actions tab → "Daily data collection" → "Run workflow". Watch the run logs. Verify:
- No errors
- A new commit appears with `data: update DD/MM/YY`
- Dashboard loads with fresh data
- Daily email arrives in inbox

**Step 7: Verify weekly email**

Go to "Weekly summary email" → "Run workflow". Check inbox for weekly summary.

---

## Final verification checklist

```bash
# Run all tests
pytest -v

# Dry run orchestrator locally (collects data, does not commit or email)
python orchestrator.py --dry-run

# Check data was written
cat data/latest.json | python -m json.tool | head -40
```

Expected test output: all PASS, no errors.
