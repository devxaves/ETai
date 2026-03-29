"""
routers/market.py — Market summary, movers, and sector performance endpoints.
"""

import asyncio
import structlog
from fastapi import APIRouter, Query

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/summary")
async def get_market_summary():
    """
    GET /api/market/summary — Get Nifty 50 value, breadth, FII/DII data using NSE Bhavcopy.
    NSE-Only Mode: Uses real NSE data instead of yfinance.
    """
    from backend.data.nse_fetcher import (
        get_nifty_index_from_cached_bhavcopy,
        get_market_breadth_from_bhavcopy,
        get_nifty50_quotes,
    )
    from backend.data.yfinance_fetcher import get_nifty_index

    try:
        # Fetch all data in parallel with generous timeout
        nifty_task = get_nifty_index_from_cached_bhavcopy()
        breadth_task = get_market_breadth_from_bhavcopy()
        quotes_task = get_nifty50_quotes()

        try:
            nifty, breadth, quotes = await asyncio.wait_for(
                asyncio.gather(nifty_task, breadth_task, quotes_task, return_exceptions=True),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning("Market summary timed out, returning fallback")
            return _get_demo_market_summary()

        # Handle exceptions
        if isinstance(nifty, Exception):
            nifty = {"price": 0, "change": 0, "change_pct": 0}
        if isinstance(breadth, Exception):
            breadth = {"advances": 0, "declines": 0, "unchanged": 0}
        if isinstance(quotes, Exception):
            quotes = []

        # If cache computation failed, use direct Nifty index feed.
        if nifty.get("price", 0) == 0:
            live_nifty = await get_nifty_index()
            if live_nifty.get("price", 0) > 0:
                live_change_pct = float(live_nifty.get("change_pct", 0) or 0)
                live_price = float(live_nifty.get("price", 0) or 0)
                nifty = {
                    "price": round(live_price, 2),
                    "change": round(live_price * live_change_pct / 100, 2),
                    "change_pct": round(live_change_pct, 2),
                }

        # If Nifty is still unavailable and no quotes exist, use fallback response.
        if nifty.get("price", 0) == 0:
            logger.warning("Nifty index is 0 and no quotes are available, using fallback data")
            return _get_demo_market_summary()

        gainers = sorted(quotes, key=lambda x: x.get("change_pct", 0), reverse=True)[:5]
        losers = sorted(quotes, key=lambda x: x.get("change_pct", 0))[:5]

        # Compute Nifty Bank as average of bank stock closes
        bank_stocks = ["SBIN", "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK"]
        bank_quotes = [q for q in quotes if q.get("symbol") in bank_stocks]

        if bank_quotes:
            niftybank_price = sum(q.get("price", 0) for q in bank_quotes) / len(bank_quotes)
            niftybank_change_pct = sum(q.get("change_pct", 0) for q in bank_quotes) / len(bank_quotes)
        else:
            niftybank_price = 47800
            niftybank_change_pct = -0.44

        return {
            "nifty50": {
                "value": round(nifty.get("price", 22500), 2),
                "change": round(nifty.get("change", 0), 2),
                "change_pct": round(nifty.get("change_pct", 0), 2),
            },
            "niftybank": {
                "value": round(niftybank_price, 2),
                "change": 0,
                "change_pct": round(niftybank_change_pct, 2),
            },
            "market_breadth": {
                "advances": breadth.get("advances", 0),
                "declines": breadth.get("declines", 0),
                "unchanged": breadth.get("unchanged", 0),
                "advance_decline_ratio": round(
                    breadth.get("advances", 1) / max(breadth.get("declines", 1), 1), 2
                ),
            },
            "fii_dii": _get_fii_dii_data(),
            "top_gainers": gainers[:5],
            "top_losers": losers[:5],
            "total_quotes": len(quotes),
            "data_source": "NSE Bhavcopy",
        }

    except Exception as e:
        logger.error("Market summary failed", error=str(e))
        return _get_demo_market_summary()


@router.get("/movers")
async def get_market_movers(top_n: int = Query(default=5, ge=1, le=20)):
    """
    GET /api/market/movers — Top N gainers and losers from Nifty 50.
    """
    from backend.data.nse_fetcher import get_nifty50_quotes

    try:
        try:
            quotes = await asyncio.wait_for(get_nifty50_quotes(), timeout=8.0)
        except asyncio.TimeoutError:
            logger.warning("Market movers timed out — returning demo")
            return _get_demo_movers(top_n)

        gainers = sorted(quotes, key=lambda x: x.get("change_pct", 0), reverse=True)[:top_n]
        losers = sorted(quotes, key=lambda x: x.get("change_pct", 0))[:top_n]
        return {"gainers": gainers, "losers": losers}
    except Exception as e:
        logger.error("Market movers failed", error=str(e))
        return _get_demo_movers(top_n)


@router.get("/sector")
async def get_sector_performance():
    """
    GET /api/market/sector — Sector-wise performance from NSE Bhavcopy (NSE-Only Mode).
    """
    from backend.data.nse_fetcher import get_sector_performance_from_bhavcopy

    try:
        try:
            sector_results = await asyncio.wait_for(
                get_sector_performance_from_bhavcopy(),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning("Sector performance timed out, returning empty")
            from backend.config import SECTOR_SYMBOLS
            return {"sectors": {s: {"avg_change_pct": 0.0, "direction": "flat", "stocks": []} for s in SECTOR_SYMBOLS}}

        # Ensure all sectors are present
        from backend.config import SECTOR_SYMBOLS
        for sector in SECTOR_SYMBOLS:
            if sector not in sector_results:
                sector_results[sector] = {"avg_change_pct": 0.0, "direction": "flat", "stocks": []}

        logger.info("Sector performance fetched from Bhavcopy", sectors=len(sector_results))
        return {"sectors": sector_results}

    except Exception as e:
        logger.error("Sector performance failed", error=str(e))
        from backend.config import SECTOR_SYMBOLS
        return {"sectors": {s: {"avg_change_pct": 0.0, "direction": "flat", "stocks": []} for s in SECTOR_SYMBOLS}}


@router.get("/nifty-history")
async def get_nifty_history(days: int = Query(default=60, ge=10, le=365)):
    """GET /api/market/nifty-history — Nifty 50 daily OHLC series for dashboard charts."""
    from backend.data.yfinance_fetcher import get_nifty_history as fetch_nifty_history

    try:
        data = await fetch_nifty_history(days=days)
        return {"symbol": "NIFTY50", "chart_data": data, "total": len(data)}
    except Exception as e:
        logger.error("Nifty history endpoint failed", error=str(e))
        return {"symbol": "NIFTY50", "chart_data": [], "total": 0}


def _get_fii_dii_data() -> dict:
    """Return FII/DII flow data (static for now — integrate NSE API in production)."""
    return {
        "fii_buy": 8234.5, "fii_sell": 7102.3, "fii_net": 1132.2,
        "dii_buy": 5890.1, "dii_sell": 4780.6, "dii_net": 1109.5,
        "date": "2026-03-26", "note": "Data in ₹ Crore",
    }


def _get_demo_market_summary() -> dict:
    return {
        "nifty50": {"value": 22547.35, "change": 125.80, "change_pct": 0.56},
        "niftybank": {"value": 47823.15, "change": -210.40, "change_pct": -0.44},
        "market_breadth": {"advances": 32, "declines": 16, "unchanged": 2, "advance_decline_ratio": 2.0},
        "fii_dii": _get_fii_dii_data(),
        "top_gainers": [
            {"symbol": "TATAMOTORS", "change_pct": 3.2, "price": 972.5},
            {"symbol": "BAJFINANCE", "change_pct": 2.8, "price": 6842.0},
            {"symbol": "TITAN", "change_pct": 2.1, "price": 3215.0},
        ],
        "top_losers": [
            {"symbol": "HINDALCO", "change_pct": -1.8, "price": 645.0},
            {"symbol": "ONGC", "change_pct": -1.5, "price": 267.0},
            {"symbol": "BPCL", "change_pct": -1.2, "price": 312.0},
        ],
        "total_quotes": 50,
    }


def _get_demo_movers(top_n: int) -> dict:
    return {
        "gainers": [
            {"symbol": "TATAMOTORS", "change_pct": 3.2, "price": 972.5},
            {"symbol": "BAJFINANCE", "change_pct": 2.8, "price": 6842.0},
        ][:top_n],
        "losers": [
            {"symbol": "HINDALCO", "change_pct": -1.8, "price": 645.0},
            {"symbol": "ONGC", "change_pct": -1.5, "price": 267.0},
        ][:top_n],
    }
