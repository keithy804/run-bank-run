import json
import logging
import os
import re
import resend
from datetime import datetime, timedelta
from config import RESEND_API_KEY, EMAIL_TO, DASHBOARD_URL, BANKS

logger = logging.getLogger(__name__)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

STATUS_SYMBOL = {"green": "🟢", "amber": "🟡", "red": "🔴", "error": "⚪"}


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

    snap         = data["snapshot"]
    week_alerts  = data["week_alerts"]
    week_changes = data["week_price_changes"]
    sonia_avg    = data["sonia_week_avg"]

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

    snapshot     = load_latest_snapshot()
    week_ago     = load_history_snapshot(7)
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
        "from": "Bank Monitor <onboarding@resend.dev>",
        "to": EMAIL_TO,
        "subject": build_subject(),
        "html": build_weekly_html(data),
    })
    logger.info("Weekly email sent")
