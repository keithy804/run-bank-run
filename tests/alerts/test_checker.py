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
