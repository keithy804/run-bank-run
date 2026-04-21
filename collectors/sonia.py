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
        headers = {"User-Agent": "Mozilla/5.0 (compatible; bank-monitor/1.0)"}
        resp = requests.get(BOE_SONIA_URL, headers=headers, timeout=30)
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
