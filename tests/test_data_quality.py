# tests/test_data_quality.py
import json
import os
import pytest

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "latest.json")

BANK_KEYS   = {"BARC.L", "LLOY.L", "NWG.L", "HSBA.L"}
BANK_FIELDS = {
    "name", "price", "change_pct_1d", "change_pct_5d", "change_pct_30d",
    "week_52_high", "week_52_low", "history_90d", "status",
}
SONIA_FIELDS = {"rate", "change_1d", "history_90d", "status"}
BOE_FIELDS   = {"ccyb_rate", "next_fsr_date", "next_ccyb_decision", "recent_announcements"}
TOP_KEYS     = {"updated_at", "prices", "sonia", "news", "boe", "alerts", "overall_status"}
VALID_STATUS = {"green", "amber", "red"}


@pytest.fixture(scope="module")
def data():
    with open(DATA_FILE) as f:
        return json.load(f)


def test_top_level_keys_present(data):
    missing = TOP_KEYS - data.keys()
    assert not missing, f"Missing top-level keys: {missing}"


def test_all_banks_present(data):
    missing = BANK_KEYS - data["prices"].keys()
    assert not missing, f"Missing bank entries: {missing}"


def test_each_bank_has_required_fields(data):
    for sym, bank in data["prices"].items():
        missing = BANK_FIELDS - bank.keys()
        assert not missing, f"{sym} missing fields: {missing}"


def test_sonia_has_required_fields(data):
    missing = SONIA_FIELDS - data["sonia"].keys()
    assert not missing, f"SONIA missing fields: {missing}"


def test_boe_has_required_fields(data):
    missing = BOE_FIELDS - data["boe"].keys()
    assert not missing, f"BoE missing fields: {missing}"


def test_news_is_list(data):
    assert isinstance(data["news"], list), "news must be a list"


def test_overall_status_is_valid(data):
    assert data["overall_status"] in VALID_STATUS, \
        f"overall_status '{data['overall_status']}' not in {VALID_STATUS}"
