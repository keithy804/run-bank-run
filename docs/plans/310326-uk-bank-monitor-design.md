# UK Bank Stability Monitor — Design

Date: 31/03/26

## Overview

A personal early-warning dashboard tracking the financial health of the Big 4 UK banks using freely available data. Runs on a daily schedule, serves a static dashboard via GitHub Pages, and delivers email summaries (daily weekdays + weekly Sundays).

---

## Architecture

**Approach: Modular pipeline + static JS dashboard**

GitHub Actions triggers the orchestrator each weekday morning at 7am UTC. Four independent collectors fetch data, each wrapped in try/except so a single failure does not block the others. Results merge into a shared JSON structure, alerts are evaluated, and two files are written and committed: `data/latest.json` (always overwritten) and `data/history/DDMMYY.json` (one per day). GitHub Pages serves the static dashboard immediately from the updated JSON. Email is sent last so a failure there never blocks data collection.

---

## Directory Structure

```
run-bank-run/
├── .github/workflows/
│   ├── daily.yml          # Mon–Fri 7am UTC: collect + daily email
│   └── weekly.yml         # Sun 7am UTC: weekly summary email
├── collectors/
│   ├── prices.py          # yfinance — BARC.L, LLOY.L, NWG.L, HSBA.L
│   ├── sonia.py           # BoE Statistical API
│   ├── news.py            # RSS: BBC Business, Reuters, BoE
│   └── boe.py             # BoE CCyB, FSR dates, announcements
├── alerts/
│   └── checker.py         # Evaluates thresholds, returns triggered alerts
├── email/
│   ├── daily.py           # Daily email builder
│   ├── weekly.py          # Weekly email builder
│   └── templates/         # HTML email templates
├── data/
│   ├── latest.json        # Current snapshot — served by GitHub Pages
│   └── history/           # DDMMYY.json per day
├── index.html             # Static dashboard (Chart.js reads latest.json)
├── orchestrator.py        # Main entry point
├── config.py              # Thresholds, bank list, email settings
└── requirements.txt
```

`index.html` lives at the repo root so GitHub Pages serves it as the homepage, and `fetch('/data/latest.json')` works as a relative path.

---

## Data Schema

### `data/latest.json`

```json
{
  "updated_at": "2026-03-31T07:30:00Z",
  "prices": {
    "BARC.L": {
      "name": "Barclays",
      "price": 210.50,
      "change_pct_1d": -0.8,
      "change_pct_5d": -2.1,
      "change_pct_30d": 5.3,
      "week_52_high": 280.0,
      "week_52_low": 160.0,
      "history_30d": [209.1, 211.3],
      "status": "green"
    }
  },
  "sonia": {
    "rate": 5.19,
    "change_1d": 0.01,
    "history_30d": [5.18, 5.19],
    "status": "green"
  },
  "news": [
    {
      "title": "...",
      "source": "BBC Business",
      "url": "...",
      "published_at": "310326-0600"
    }
  ],
  "boe": {
    "ccyb_rate": 2.0,
    "next_fsr_date": "011124",
    "recent_announcements": []
  },
  "alerts": [
    {
      "type": "price_drop_daily",
      "bank": "BARC.L",
      "message": "Barclays dropped 6.2% today",
      "severity": "red"
    }
  ],
  "overall_status": "amber"
}
```

`history_30d` arrays are read directly by Chart.js — no secondary fetch needed.

### `overall_status` logic

- `red` — any red alert active
- `amber` — any amber alert, or any collector returned an error
- `green` — all clear

---

## Dashboard

Single scrolling page, mobile-first. Sections:

1. **Header** — title + last updated timestamp. Stale-data warning if `updated_at` > 48 hours old.
2. **Alerts banner** — high-contrast red/amber bar, only shown when alerts are active.
3. **Bank cards** — 2×2 grid on mobile, 4-across on desktop. Each card: name, price, 1d % change, traffic light status (colour + symbol).
4. **Share price chart** — all four banks on one Chart.js line chart. Toggle buttons: 7d / 30d / 90d.
5. **SONIA chart** — 30-day line chart.
6. **Headlines** — list of up to 10 items with source label and link.
7. **BoE footer** — CCyB rate, next FSR date.

**Dyslexia-friendly rules:** system sans-serif font, 16px minimum, 1.6 line-height, status uses colour + symbol (never colour alone), no dense tables, generous padding. Chart animations disabled.

---

## RSS News Sources

Feeds filtered by keywords: *bank, barclays, lloyds, natwest, hsbc, banking, financial stability, bank of england*. Returns 10 most recent matching items across all sources.

- BBC Business: `https://feeds.bbci.co.uk/news/business/rss.xml`
- Reuters UK: `https://feeds.reuters.com/reuters/UKBusinessNews`
- Bank of England: `https://www.bankofengland.co.uk/rss/publications`

---

## Email

### Daily (Mon–Fri ~7:30am UK time)

Subject: `Bank Monitor — 31/03/26 ✅ All Clear` or `⚠ 1 Alert`

Sections: alerts (if any) → bank prices (one line each with status symbol) → SONIA rate → top 3 headlines → dashboard link.

### Weekly (Sunday ~7:30am UK time)

Subject: `Bank Monitor — Week of 23/03/26 📊`

Sections: week-over-week % changes per bank → SONIA average → alerts triggered this week → upcoming BoE events → plain-English summary (template-generated, no LLM) → dashboard link.

Both emails: clean HTML with inline styles, single-column, large fonts, mobile-friendly.

---

## Config (`config.py`)

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

DASHBOARD_URL = "https://<github-username>.github.io/run-bank-run/"
```

Secrets (`RESEND_API_KEY`, `EMAIL_TO`) from GitHub Actions environment variables — never hardcoded.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Collector throws exception | Log error, mark section `"status": "error"`, continue |
| yfinance rate-limited | Retry once after 30s, then mark as error |
| RSS feed unreachable | Skip that feed, use others |
| No news items found | Dashboard shows "No recent headlines" — not an error |
| Resend API fails | Log error, do not retry, do not block commit |
| Git push fails | Retry once, then fail the Action (triggers GitHub notification) |

---

## Out of Scope

- CDS spread automation (manual check: investing.com)
- Multi-user support
- Mobile app
- Real-time streaming
- Trading or investment recommendations
- Coverage beyond Big 4

---

## Success Criteria

1. Data collected automatically each weekday without manual intervention
2. Dashboard reflects data no older than 24 hours on any weekday
3. Daily email arrives before 9am UK time on weekdays
4. Weekly email arrives Sunday mornings
5. Alerts fire correctly when thresholds are breached
6. Total monthly cost: zero
