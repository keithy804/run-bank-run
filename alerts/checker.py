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
