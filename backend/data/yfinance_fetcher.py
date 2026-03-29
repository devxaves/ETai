"""
data/yfinance_fetcher.py — Dedicated yfinance wrapper for live market quotes.
"""

import asyncio
from datetime import date, timedelta
import yfinance as yf
import structlog

logger = structlog.get_logger(__name__)


async def get_ticker_info(symbol: str) -> dict:
    """Get full ticker info from yfinance."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = await asyncio.to_thread(lambda: ticker.info)
        return info or {}
    except Exception as e:
        logger.warning("Ticker info failed", symbol=symbol, error=str(e))
        return {}


async def get_nifty_index() -> dict:
    """Get Nifty 50 index data."""
    try:
        ticker = yf.Ticker("^NSEI")
        info = await asyncio.to_thread(lambda: ticker.fast_info)
        price = float(getattr(info, "last_price", 0) or 0)
        change_pct = float(getattr(info, "regular_market_change_percent", 0) or 0)

        # If fast_info is incomplete, derive missing values from recent history.
        if price <= 0 or change_pct == 0:
            hist = await asyncio.to_thread(lambda: ticker.history(period="5d", interval="1d"))
            if not hist.empty:
                close_series = hist["Close"].dropna()
                if price <= 0 and len(close_series) >= 1:
                    price = float(close_series.iloc[-1])
                if len(close_series) >= 2 and close_series.iloc[-2] != 0:
                    change_pct = float(((close_series.iloc[-1] - close_series.iloc[-2]) / close_series.iloc[-2]) * 100)

        return {
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        logger.warning("Nifty index fetch failed", error=str(e))
        return {"price": 0, "change_pct": 0}


async def get_nifty_history(days: int = 60) -> list[dict]:
    """Get Nifty 50 OHLC history for dashboard charting."""
    try:
        ticker = yf.Ticker("^NSEI")
        period_days = max(days + 10, 30)
        hist = await asyncio.to_thread(
            lambda: ticker.history(period=f"{period_days}d", interval="1d", auto_adjust=True)
        )
        if hist.empty:
            return []

        hist = hist.reset_index()
        output = []
        for _, row in hist.tail(days).iterrows():
            dt = row.get("Date")
            if dt is None:
                continue
            ts = int(dt.timestamp()) if hasattr(dt, "timestamp") else int((date.today() - timedelta(days=1)).strftime("%s"))
            output.append(
                {
                    "time": ts,
                    "open": float(row.get("Open", 0) or 0),
                    "high": float(row.get("High", 0) or 0),
                    "low": float(row.get("Low", 0) or 0),
                    "close": float(row.get("Close", 0) or 0),
                    "volume": float(row.get("Volume", 0) or 0),
                }
            )

        return [r for r in output if r["open"] > 0 and r["high"] > 0 and r["low"] > 0 and r["close"] > 0]
    except Exception as e:
        logger.warning("Nifty history fetch failed", error=str(e))
        return []
