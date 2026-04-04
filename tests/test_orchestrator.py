import json
import os
import pytest
from unittest.mock import patch, MagicMock
from orchestrator import build_snapshot, write_json_files

def _dummy_prices():
    return {sym: {"name": n, "price": 100.0, "change_pct_1d": 0.0, "change_pct_5d": 0.0,
                  "change_pct_30d": 0.0, "week_52_high": 120.0, "week_52_low": 80.0,
                  "history_90d": [100.0], "status": "green"}
            for sym, n in [("BARC.L","Barclays"),("LLOY.L","Lloyds"),
                           ("NWG.L","NatWest"),("HSBA.L","HSBC")]}

def _dummy_sonia():
    return {"rate": 5.19, "change_1d": 0.01, "history_90d": [5.19], "status": "green"}

def test_build_snapshot_has_required_keys():
    snap = build_snapshot(
        prices=_dummy_prices(),
        sonia=_dummy_sonia(),
        news=[],
        boe={"ccyb_rate": 2.0, "next_fsr_date": "Nov 2026",
             "next_ccyb_decision": "Q2 2026", "recent_announcements": []},
    )
    for key in ("updated_at", "prices", "sonia", "news", "boe", "alerts", "overall_status"):
        assert key in snap

def test_write_json_files_creates_latest_and_history(tmp_path):
    snap = {"updated_at": "2026-03-31T07:00:00Z", "prices": {}}
    write_json_files(snap, data_dir=str(tmp_path))
    assert (tmp_path / "latest.json").exists()
    history_files = list((tmp_path / "history").glob("*.json"))
    assert len(history_files) == 1

def test_write_json_files_latest_is_valid_json(tmp_path):
    snap = {"updated_at": "2026-03-31T07:00:00Z"}
    write_json_files(snap, data_dir=str(tmp_path))
    with open(tmp_path / "latest.json") as f:
        loaded = json.load(f)
    assert loaded["updated_at"] == "2026-03-31T07:00:00Z"
