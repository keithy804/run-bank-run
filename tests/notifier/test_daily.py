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
