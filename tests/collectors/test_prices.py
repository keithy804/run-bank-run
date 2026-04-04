import pandas as pd
import pytest
from collectors.prices import fetch_prices

def _make_mock_ticker(mocker, closes, high_52w=280.0, low_52w=160.0):
    dates = pd.date_range(end="2026-03-31", periods=len(closes), freq="B")
    hist = pd.DataFrame({"Close": closes}, index=dates)
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = hist
    mock_ticker.info = {"fiftyTwoWeekHigh": high_52w, "fiftyTwoWeekLow": low_52w}
    return mock_ticker

def test_fetch_prices_returns_all_banks(mocker):
    mock_ticker = _make_mock_ticker(mocker, [200.0, 205.0, 210.0])
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = fetch_prices()
    assert set(result.keys()) == {"BARC.L", "LLOY.L", "NWG.L", "HSBA.L"}

def test_fetch_prices_correct_structure(mocker):
    mock_ticker = _make_mock_ticker(mocker, [200.0, 205.0, 210.0])
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = fetch_prices()
    bank = result["BARC.L"]
    assert bank["name"] == "Barclays"
    assert bank["price"] == 210.0
    assert "change_pct_1d" in bank
    assert "change_pct_5d" in bank
    assert "change_pct_30d" in bank
    assert bank["week_52_high"] == 280.0
    assert bank["week_52_low"] == 160.0
    assert "history_90d" in bank
    assert bank["status"] in ("green", "amber", "red")

def test_fetch_prices_change_pct_1d_calculation(mocker):
    # 200 -> 210 = +5%
    mock_ticker = _make_mock_ticker(mocker, [200.0, 210.0])
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = fetch_prices()
    assert result["BARC.L"]["change_pct_1d"] == pytest.approx(5.0)

def test_fetch_prices_returns_error_on_exception(mocker):
    mocker.patch("yfinance.Ticker", side_effect=Exception("API error"))
    result = fetch_prices()
    for bank in result.values():
        assert bank["status"] == "error"
