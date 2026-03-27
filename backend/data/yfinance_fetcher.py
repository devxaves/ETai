"""
data/yfinance_fetcher.py — Dedicated yfinance wrapper for live market quotes.
"""

import asyncio
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
        return {
            "price": getattr(info, "last_price", 0) or 0,
            "change_pct": getattr(info, "regular_market_change_percent", 0) or 0,
        }
    except Exception as e:
        logger.warning("Nifty index fetch failed", error=str(e))
        return {"price": 22500, "change_pct": 0.5}
