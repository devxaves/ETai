"""
routers/patterns.py — Chart pattern endpoints with OHLCV data for frontend charting.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import PatternHistory

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/patterns", tags=["patterns"])

# Cached Nifty 50 scan results (refreshed by Celery)
_nifty50_cache: dict = {"patterns": [], "last_updated": None}


@router.get("/nifty50")
async def get_nifty50_patterns(db: AsyncSession = Depends(get_db)):
    """
    GET /api/patterns/nifty50 — Pre-computed Nifty 50 patterns (fast, cached).
    Returns top 10 patterns detected across all Nifty 50 stocks.
    """
    # Return cache if fresh (within last hour)
    import time
    if _nifty50_cache["last_updated"] and time.time() - _nifty50_cache["last_updated"] < 3600:
        return {"patterns": _nifty50_cache["patterns"], "source": "cache", "total": len(_nifty50_cache["patterns"])}

    # Pull from DB (populated by Celery)
    stmt = select(PatternHistory).order_by(desc(PatternHistory.detected_at)).limit(10)
    result = await db.execute(stmt)
    patterns = result.scalars().all()

    if patterns:
        data = [
            {
                "symbol": p.symbol, "pattern_name": p.pattern_name,
                "success_rate": p.success_rate, "confidence_score": p.confidence_score,
                "price_at_detection": p.price_at_detection, "detected_at": p.detected_at.isoformat(),
                "raw_data": p.raw_data or {},
            }
            for p in patterns
        ]
        _nifty50_cache["patterns"] = data
        _nifty50_cache["last_updated"] = time.time()
        return {"patterns": data, "source": "db", "total": len(data)}

    # No cached data — run live (slower)
    from backend.agents.chart_patterns import ChartPatternAgent
    agent = ChartPatternAgent()
    patterns_live = await agent.scan_nifty50()
    _nifty50_cache["patterns"] = patterns_live
    _nifty50_cache["last_updated"] = time.time()

    return {"patterns": patterns_live, "source": "live", "total": len(patterns_live)}


@router.get("/scan")
async def scan_symbols(
    symbols: str = Query(..., description="Comma-separated NSE symbols, e.g. RELIANCE,TCS,INFY"),
    background_tasks: BackgroundTasks = None,
):
    """
    GET /api/patterns/scan?symbols=RELIANCE,TCS,INFY
    Scan specific symbols for current patterns.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol required")
    if len(symbol_list) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 symbols per request")

    from backend.agents.chart_patterns import ChartPatternAgent
    import asyncio

    agent = ChartPatternAgent()
    tasks = [agent.scan_symbol(sym) for sym in symbol_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_patterns = []
    for sym, result in zip(symbol_list, results):
        if isinstance(result, list):
            for p in result:
                all_patterns.append(p.to_dict())

    all_patterns.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)

    return {
        "symbols_scanned": symbol_list,
        "patterns": all_patterns,
        "total": len(all_patterns),
    }


@router.get("/{symbol}")
async def get_symbol_patterns(
    symbol: str,
    days: int = Query(default=60, ge=10, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/patterns/{symbol}?days=60
    Get all patterns for a symbol with OHLCV chart data.
    """
    symbol = symbol.upper().strip()

    from backend.agents.chart_patterns import ChartPatternAgent
    import asyncio

    agent = ChartPatternAgent()

    # Run scan + fetch chart data in parallel
    patterns_task = agent.scan_symbol(symbol)
    chart_task = agent.get_chart_data(symbol, days=days)
    patterns, chart_data = await asyncio.gather(patterns_task, chart_task, return_exceptions=True)

    if isinstance(patterns, Exception):
        logger.error("Pattern scan error", symbol=symbol, error=str(patterns))
        patterns = []

    if isinstance(chart_data, Exception):
        logger.error("Chart data error", symbol=symbol, error=str(chart_data))
        chart_data = []

    # Build pattern list with backtest info
    pattern_dicts = []
    for p in (patterns or []):
        pat_dict = p.to_dict()
        if not pat_dict.get("success_rate"):
            try:
                pat_dict["success_rate"] = await agent.backtest_pattern(symbol, p.pattern_name)
            except Exception:
                pat_dict["success_rate"] = 50.0
        pattern_dicts.append(pat_dict)

    return {
        "symbol": symbol,
        "patterns": pattern_dicts,
        "chart_data": chart_data,
        "patterns_count": len(pattern_dicts),
        "days_fetched": days,
    }
