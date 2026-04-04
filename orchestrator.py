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
        "updated_at": snapshot.get("updated_at"),
        "prices": {sym: {k: v for k, v in bank.items() if k != "history_90d"}
                   for sym, bank in snapshot.get("prices", {}).items()},
        "sonia": {k: v for k, v in snapshot.get("sonia", {}).items() if k != "history_90d"},
        "alerts": snapshot.get("alerts", []),
        "overall_status": snapshot.get("overall_status", "green"),
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
