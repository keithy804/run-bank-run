import logging
import os
import re
import resend
from datetime import datetime
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
        .replace("{{alert_block}}", alert_block)
        .replace("{{banks}}", bank_rows)
        .replace("{{news}}", news_rows)
        .replace("{{sonia_rate}}", str(sonia_rate))
        .replace("{{sonia_direction}}", sonia_dir)
        .replace("{{sonia_change}}", f"{abs(sonia_change):.3f}")
        .replace("{{sonia_status_class}}", sonia_cls)
        .replace("{{dashboard_url}}", DASHBOARD_URL)
    )

    # Clean up any unfilled placeholders
    html = re.sub(r"\{\{[^}]+\}\}", "", html)
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
