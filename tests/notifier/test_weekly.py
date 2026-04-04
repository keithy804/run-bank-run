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
