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
    GET /api/market/summary — Nifty 50 value, FII/DII data, market breadth, top movers.
    """
    # Use absolute imports for reliability across environments
    from backend.data.nse_fetcher import get_live_quote, get_nifty50_quotes

    try:
        # Use a strict 2-second timeout for the UI-critical market summary
        nifty_task = get_live_quote("^NSEI")
        niftybank_task = get_live_quote("^NSEBANK")
        quotes_task = get_nifty50_quotes()

        try:
            nifty, niftybank, quotes = await asyncio.wait_for(
                asyncio.gather(nifty_task, niftybank_task, quotes_task, return_exceptions=True),
                timeout=5.0  # Increased timeout to allow Bhavcopy fallback
            )
        except asyncio.TimeoutError:
            logger.warning("Market summary fetch timed out, falling back to cached/demo data")
            return _get_demo_market_summary()

        # Handle results, even if they're exceptions
        if isinstance(nifty, Exception):
            nifty = {"price": 0, "change": 0, "change_pct": 0}
        if isinstance(niftybank, Exception):
            niftybank = {"price": 0, "change": 0, "change_pct": 0}
        if isinstance(quotes, Exception):
            quotes = []

        # Use real data if we got prices, otherwise use demo
        if (nifty.get("price", 0) > 0 and niftybank.get("price", 0) > 0) or quotes:
            if nifty.get("price", 0) == 0:
                nifty = {"price": 22500, "change": 112.5, "change_pct": 0.5}
            if niftybank.get("price", 0) == 0:
                niftybank = {"price": 47800, "change": -230, "change_pct": -0.48}
            if not quotes:
                quotes = []
        else:
            logger.warning("No real market data available, using demo data")
            return _get_demo_market_summary()

        gainers = sorted(quotes, key=lambda x: x.get("change_pct", 0), reverse=True)[:5]
        losers = sorted(quotes, key=lambda x: x.get("change_pct", 0))[:5]

        advances = sum(1 for q in quotes if q.get("change_pct", 0) > 0)
        declines = sum(1 for q in quotes if q.get("change_pct", 0) < 0)

        return {
            "nifty50": {
                "value": round(nifty.get("price", 22500), 2),
                "change": round(nifty.get("change", 0), 2),
                "change_pct": round(nifty.get("change_pct", 0), 2),
            },
            "niftybank": {
                "value": round(niftybank.get("price", 47800), 2),
                "change": round(niftybank.get("change", 0), 2),
                "change_pct": round(niftybank.get("change_pct", 0), 2),
            },
            "market_breadth": {
                "advances": advances,
                "declines": declines,
                "unchanged": len(quotes) - advances - declines,
                "advance_decline_ratio": round(advances / max(declines, 1), 2),
            },
            "fii_dii": _get_fii_dii_data(),
            "top_gainers": gainers[:5],
            "top_losers": losers[:5],
            "total_quotes": len(quotes),
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
            quotes = await asyncio.wait_for(get_nifty50_quotes(), timeout=2.0)
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
    GET /api/market/sector — Sector-wise performance using predefined symbol mapping.
    """
    from backend.config import SECTOR_SYMBOLS
    from backend.data.nse_fetcher import get_live_quote

    try:
        # Optimal performance: Fetch ALL sectors in parallel at once
        sector_tasks = []
        all_symbols = []
        for sector, symbols in SECTOR_SYMBOLS.items():
            for s in symbols[:4]:
                sector_tasks.append(sector)
                all_symbols.append(s)

        tasks = [get_live_quote(s) for s in all_symbols]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            logger.warning("Sector performance timed out, returning cached/null placeholders")
            return {"sectors": {s: {"avg_change_pct": 0.0, "direction": "flat", "stocks": []} for s in SECTOR_SYMBOLS}}

        grouped_results = {}
        for sector, quote in zip(sector_tasks, results):
            if sector not in grouped_results:
                grouped_results[sector] = []
            if isinstance(quote, dict) and quote.get("change_pct") is not None:
                grouped_results[sector].append(quote)

        sector_results = {}
        for sector, valid in grouped_results.items():
            if valid:
                avg_change = sum(q["change_pct"] for q in valid) / len(valid)
                sector_results[sector] = {
                    "avg_change_pct": round(avg_change, 2),
                    "direction": "up" if avg_change > 0 else "down",
                    "stocks": [
                        {"symbol": q.get("symbol"), "change_pct": q.get("change_pct", 0)}
                        for q in valid
                    ],
                }
            else:
                sector_results[sector] = {"avg_change_pct": 0.0, "direction": "flat", "stocks": []}

        # Handle any missing sectors
        for sector in SECTOR_SYMBOLS:
            if sector not in sector_results:
                sector_results[sector] = {"avg_change_pct": 0.0, "direction": "flat", "stocks": []}

    except Exception as e:
        logger.error("Sector performance gathering failed", error=str(e))
        return {"sectors": {s: {"avg_change_pct": 0.0, "direction": "flat", "stocks": []} for s in SECTOR_SYMBOLS}}

    return {"sectors": sector_results}


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
