import pytest
from collectors.sonia import fetch_sonia

MOCK_CSV = """Date,IUDSOIA
27 Mar 2026,5.1800
28 Mar 2026,5.1900
"""

MOCK_CSV_SINGLE_ROW = """Date,IUDSOIA
28 Mar 2026,5.1900
"""

def test_fetch_sonia_returns_correct_rate(mocker):
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=MOCK_CSV, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert result["rate"] == pytest.approx(5.19)

def test_fetch_sonia_calculates_1d_change(mocker):
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=MOCK_CSV, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert result["change_1d"] == pytest.approx(0.01)

def test_fetch_sonia_returns_history_90d(mocker):
    # Build a CSV with 95 rows
    rows = "\n".join(f"0{i % 28 + 1} Jan 2026,5.{i:04d}" for i in range(95))
    csv = f"Date,IUDSOIA\n{rows}\n"
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=csv, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert len(result["history_90d"]) == 90

def test_fetch_sonia_returns_error_on_exception(mocker):
    mocker.patch("requests.get", side_effect=Exception("timeout"))
    result = fetch_sonia()
    assert result["status"] == "error"
    assert result["rate"] is None

def test_fetch_sonia_no_1d_change_if_single_row(mocker):
    mocker.patch("requests.get", return_value=mocker.MagicMock(
        text=MOCK_CSV_SINGLE_ROW, status_code=200, raise_for_status=lambda: None
    ))
    result = fetch_sonia()
    assert result["change_1d"] == 0.0
