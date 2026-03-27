"""
routers/signals.py — Signal endpoints: list, detail, WebSocket live feed, manual scan.
"""

import asyncio
import json
import uuid
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Signal

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/signals", tags=["signals"])

# Track connected WebSocket clients
_ws_clients: list[WebSocket] = []


@router.get("")
async def get_signals(
    limit: int = Query(default=20, le=100),
    min_confidence: float = Query(default=0.0, ge=0, le=100),
    signal_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/signals — List latest signals with optional filters.

    Args:
        limit: Max signals to return (default 20, max 100).
        min_confidence: Minimum confidence score filter.
        signal_type: Filter by type (BULK_DEAL, CHART_PATTERN, INSIDER_PATTERN).
    """
    stmt = (
        select(Signal)
        .where(Signal.confidence_score >= min_confidence)
        .order_by(desc(Signal.created_at))
        .limit(limit)
    )
    if signal_type:
        stmt = stmt.where(Signal.signal_type == signal_type.upper())

    result = await db.execute(stmt)
    signals = result.scalars().all()

    return {
        "signals": [
            {
                "id": s.id, "symbol": s.symbol, "signal_type": s.signal_type,
                "description": s.description, "confidence_score": s.confidence_score,
                "is_bullish": s.is_bullish, "created_at": s.created_at.isoformat(),
                "has_explanation": bool(s.explanation),
            }
            for s in signals
        ],
        "total": len(signals),
    }


@router.get("/live-demo")
async def get_live_demo_signals():
    """Return hardcoded demo signals for when DB is empty (for judging demos)."""
    from datetime import datetime, timedelta
    import random

    demo_signals = [
        {"symbol": "RELIANCE", "signal_type": "CHART_PATTERN", "description": "Bullish Engulfing pattern detected at ₹2,847.50 — RSI at 58, MACD positive crossover", "confidence_score": 82.0, "is_bullish": True},
        {"symbol": "TCS", "signal_type": "BULK_DEAL", "description": "Unusual institutional buying: ₹1,240 Cr traded (2.8x average) — LIC of India among buyers", "confidence_score": 78.5, "is_bullish": True},
        {"symbol": "HDFCBANK", "signal_type": "INSIDER_PATTERN", "description": "Promoter group bought on 4 consecutive days — 1.2% stake acquired @ ₹1,680 avg", "confidence_score": 91.0, "is_bullish": True},
        {"symbol": "BAJFINANCE", "signal_type": "CHART_PATTERN", "description": "Morning Star pattern at key support ₹6,800 — historically 74% bullish success rate", "confidence_score": 74.0, "is_bullish": True},
        {"symbol": "INFY", "signal_type": "BULK_DEAL", "description": "Morgan Stanley increased position by 3.1% — total stake now 8.2% of free float", "confidence_score": 69.5, "is_bullish": True},
        {"symbol": "SBIN", "signal_type": "CHART_PATTERN", "description": "RSI Oversold recovery (RSI: 28→35) — Hammer pattern at ₹782 support", "confidence_score": 66.0, "is_bullish": True},
        {"symbol": "TATAMOTORS", "signal_type": "INSIDER_PATTERN", "description": "Tata Capital bought 2.3 Cr shares over 3 days — strong conviction signal", "confidence_score": 88.0, "is_bullish": True},
    ]

    now = datetime.utcnow()
    return {
        "signals": [
            {
                **s,
                "id": str(uuid.uuid4()),
                "created_at": (now - timedelta(minutes=i * 15)).isoformat(),
                "has_explanation": True,
            }
            for i, s in enumerate(demo_signals)
        ],
        "total": len(demo_signals),
    }


@router.get("/{signal_id}")
async def get_signal_detail(signal_id: str, db: AsyncSession = Depends(get_db)):
    """GET /api/signals/{signal_id} — Full signal details with LLM explanation."""
    stmt = select(Signal).where(Signal.id == signal_id)
    result = await db.execute(stmt)
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    # Generate explanation if not cached
    if not signal.explanation:
        from backend.agents.opportunity_radar import OpportunityRadarAgent
        agent = OpportunityRadarAgent()
        sig_dict = {
            "symbol": signal.symbol, "signal_type": signal.signal_type,
            "description": signal.description, "confidence_score": signal.confidence_score,
            "is_bullish": signal.is_bullish, "raw_data": signal.raw_data or {},
        }
        try:
            signal.explanation = await agent.explain_signal(sig_dict)
            await db.commit()
        except Exception as e:
            logger.warning("Explanation generation failed", error=str(e))

    return {
        "id": signal.id, "symbol": signal.symbol, "signal_type": signal.signal_type,
        "description": signal.description, "confidence_score": signal.confidence_score,
        "explanation": signal.explanation, "is_bullish": signal.is_bullish,
        "raw_data": signal.raw_data, "created_at": signal.created_at.isoformat(),
    }


@router.post("/scan")
async def trigger_manual_scan(background_tasks: BackgroundTasks):
    """POST /api/signals/scan — Trigger a manual radar scan, returns job_id."""
    job_id = str(uuid.uuid4())
    _scan_jobs[job_id] = {"status": "running", "progress": 0}

    background_tasks.add_task(_run_manual_scan, job_id)
    return {"job_id": job_id, "status": "started", "message": "Scan initiated — check /api/signals/scan/{job_id}"}


@router.get("/scan/{job_id}")
async def get_scan_status(job_id: str):
    """GET /api/signals/scan/{job_id} — Check scan job status."""
    job = _scan_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return {"job_id": job_id, **job}


# In-memory scan job tracker
_scan_jobs: dict = {}


async def _run_manual_scan(job_id: str):
    """Run a full radar scan in the background."""
    from backend.agents.opportunity_radar import OpportunityRadarAgent
    from backend.database import AsyncSessionLocal
    from backend.models import Signal

    _scan_jobs[job_id]["progress"] = 10
    try:
        async with AsyncSessionLocal() as session:
            agent = OpportunityRadarAgent(db_session=session)
            _scan_jobs[job_id]["progress"] = 30
            signals = await agent.run_full_scan()
            _scan_jobs[job_id]["progress"] = 70

            for sig_data in signals:
                session.add(Signal(
                    symbol=sig_data.get("symbol"), signal_type=sig_data.get("signal_type"),
                    description=sig_data.get("description"),
                    confidence_score=float(sig_data.get("confidence_score", 0)),
                    explanation=sig_data.get("explanation"),
                    raw_data=sig_data.get("raw_data"), is_bullish=sig_data.get("is_bullish", True),
                ))
            await session.commit()

        _scan_jobs[job_id] = {"status": "completed", "progress": 100, "signals_found": len(signals)}
        logger.info("Manual scan complete", job_id=job_id, signals=len(signals))
    except Exception as e:
        _scan_jobs[job_id] = {"status": "failed", "progress": 0, "error": str(e)}
        logger.error("Manual scan failed", job_id=job_id, error=str(e))


@router.websocket("/live")
async def websocket_live_signals(websocket: WebSocket):
    """WebSocket /api/signals/live — Real-time signal streaming via Redis pub/sub."""
    await websocket.accept()
    _ws_clients.append(websocket)

    import os
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe("signals_live")

        # Send connection confirmation
        await websocket.send_json({"type": "connected", "message": "ET Intelligence live feed connected"})

        while True:
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0)
                if message and message.get("data"):
                    data = json.loads(message["data"])
                    await websocket.send_json({"type": "signal", "data": data})
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning("WebSocket error", error=str(e))
                break

    except Exception as e:
        logger.error("WebSocket setup failed", error=str(e))
        # Fallback: send demo signals without Redis
        try:
            await websocket.send_json({"type": "connected", "message": "ET Intelligence live feed (demo mode)"})
            demo_signals = [
                {"symbol": "RELIANCE", "signal_type": "CHART_PATTERN", "confidence_score": 82.0, "description": "Bullish Engulfing detected", "is_bullish": True},
                {"symbol": "TCS", "signal_type": "BULK_DEAL", "confidence_score": 78.0, "description": "Institutional buying surge", "is_bullish": True},
            ]
            for sig in demo_signals:
                await asyncio.sleep(3)
                await websocket.send_json({"type": "signal", "data": sig})
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "heartbeat"})
        except WebSocketDisconnect:
            pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
