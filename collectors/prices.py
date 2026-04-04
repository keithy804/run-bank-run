import logging
import yfinance as yf
from config import BANKS

logger = logging.getLogger(__name__)


def _status_from_change(change_1d: float, change_5d: float) -> str:
    from config import ALERT_THRESHOLDS
    if abs(change_1d) >= ALERT_THRESHOLDS["price_drop_1d_pct"]:
        return "red"
    if abs(change_5d) >= ALERT_THRESHOLDS["price_drop_5d_pct"]:
        return "red"
    if abs(change_1d) >= ALERT_THRESHOLDS["price_drop_1d_pct"] * 0.7:
        return "amber"
    return "green"


def _pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return round((new - old) / old * 100, 2)


def fetch_prices() -> dict:
    result = {}
    for ticker_sym, name in BANKS.items():
        try:
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period="3mo")
            info = ticker.info

            if hist.empty or len(hist) < 2:
                raise ValueError("Insufficient history data")

            closes = hist["Close"].tolist()
            price = round(closes[-1], 2)
            change_1d = _pct_change(closes[-2], closes[-1])
            change_5d = _pct_change(closes[-6], closes[-1]) if len(closes) >= 6 else 0.0
            change_30d = _pct_change(closes[-31], closes[-1]) if len(closes) >= 31 else 0.0
            history_90d = [round(c, 2) for c in closes[-90:]]

            result[ticker_sym] = {
                "name": name,
                "price": price,
                "change_pct_1d": change_1d,
                "change_pct_5d": change_5d,
                "change_pct_30d": change_30d,
                "week_52_high": info.get("fiftyTwoWeekHigh", 0.0),
                "week_52_low": info.get("fiftyTwoWeekLow", 0.0),
                "history_90d": history_90d,
                "status": _status_from_change(change_1d, change_5d),
            }
        except Exception as e:
            logger.error("prices: failed to fetch %s: %s", ticker_sym, e)
            result[ticker_sym] = {
                "name": name,
                "price": None,
                "change_pct_1d": None,
                "change_pct_5d": None,
                "change_pct_30d": None,
                "week_52_high": None,
                "week_52_low": None,
                "history_90d": [],
                "status": "error",
            }
    return result
