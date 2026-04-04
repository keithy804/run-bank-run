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
