"""
tasks/scheduled.py — Celery background tasks for daily data refresh and signal detection.
"""

import asyncio
from datetime import date, datetime
import structlog

from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run an async coroutine from a Celery (sync) task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="backend.tasks.scheduled.daily_data_refresh",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def daily_data_refresh(self):
    """
    Task 1: Download latest NSE Bhavcopy + SEBI bulk deals.
    Runs at 6:00 PM IST every weekday.
    """
    logger.info("Starting daily data refresh")
    try:
        return run_async(_async_daily_data_refresh())
    except Exception as exc:
        logger.error("Daily data refresh failed", error=str(exc))
        raise self.retry(exc=exc)


async def _async_daily_data_refresh():
    """Async implementation of daily data refresh."""
    from backend.data.nse_fetcher import download_bhavcopy
    from backend.data.sebi_fetcher import fetch_bulk_deals, fetch_block_deals
    from backend.database import AsyncSessionLocal
    from backend.models import StockDaily, BulkDeal

    today = date.today()
    results = {"bhavcopy": 0, "bulk_deals": 0, "block_deals": 0}

    # Download Bhavcopy
    try:
        df = await download_bhavcopy(today)
        if not df.empty:
            async with AsyncSessionLocal() as session:
                for _, row in df.iterrows():
                    stock = StockDaily(
                        symbol=str(row.get("symbol", "")).upper().strip(),
                        date=row.get("date"),
                        open=float(row.get("open", 0) or 0),
                        high=float(row.get("high", 0) or 0),
                        low=float(row.get("low", 0) or 0),
                        close=float(row.get("close", 0) or 0),
                        volume=int(row.get("volume", 0) or 0),
                    )
                    session.add(stock)
                await session.commit()
                results["bhavcopy"] = len(df)
        logger.info("Bhavcopy stored", rows=results["bhavcopy"])
    except Exception as e:
        logger.error("Bhavcopy download failed", error=str(e))

    # Download SEBI Bulk Deals
    try:
        from datetime import timedelta
        from_date = today - timedelta(days=1)
        bulk_df = await fetch_bulk_deals(from_date, today)
        block_df = await fetch_block_deals(from_date, today)

        async with AsyncSessionLocal() as session:
            for _, row in bulk_df.iterrows():
                session.add(BulkDeal(
                    date=row.get("date"), symbol=str(row.get("symbol", "")).upper(),
                    client_name=str(row.get("client_name", "")),
                    deal_type=str(row.get("deal_type", "")),
                    quantity=float(row.get("quantity", 0) or 0),
                    price=float(row.get("price", 0) or 0),
                    deal_category="BULK",
                ))
            for _, row in block_df.iterrows():
                session.add(BulkDeal(
                    date=row.get("date"), symbol=str(row.get("symbol", "")).upper(),
                    client_name=str(row.get("client_name", "")),
                    deal_type=str(row.get("deal_type", "")),
                    quantity=float(row.get("quantity", 0) or 0),
                    price=float(row.get("price", 0) or 0),
                    deal_category="BLOCK",
                ))
            await session.commit()
            results["bulk_deals"] = len(bulk_df)
            results["block_deals"] = len(block_df)
    except Exception as e:
        logger.error("SEBI deals download failed", error=str(e))

    logger.info("Daily data refresh complete", results=results)
    return results


@celery_app.task(
    name="backend.tasks.scheduled.scan_opportunity_radar",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def scan_opportunity_radar(self):
    """
    Task 2: Run OpportunityRadarAgent and store new signals.
    Runs at 6:30 PM IST every weekday.
    """
    logger.info("Starting opportunity radar scan")
    try:
        return run_async(_async_scan_radar())
    except Exception as exc:
        logger.error("Radar scan failed", error=str(exc))
        raise self.retry(exc=exc)


async def _async_scan_radar():
    """Async implementation of opportunity radar scan."""
    from backend.agents.opportunity_radar import OpportunityRadarAgent
    from backend.database import AsyncSessionLocal
    from backend.models import Signal
    import redis.asyncio as aioredis
    import json
    import os

    async with AsyncSessionLocal() as session:
        agent = OpportunityRadarAgent(db_session=session)
        signals = await agent.run_full_scan()

        new_count = 0
        for sig_data in signals:
            signal = Signal(
                symbol=sig_data.get("symbol", ""),
                signal_type=sig_data.get("signal_type", ""),
                description=sig_data.get("description", ""),
                confidence_score=float(sig_data.get("confidence_score", 0)),
                explanation=sig_data.get("explanation"),
                raw_data=sig_data.get("raw_data"),
                is_bullish=sig_data.get("is_bullish", True),
            )
            session.add(signal)
            new_count += 1

        await session.commit()
        logger.info("Radar signals stored", count=new_count)

    # Publish to Redis pub/sub for real-time WebSocket delivery
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url)
        for sig_data in signals[:5]:  # Top 5 signals
            await r.publish("signals_live", json.dumps({
                "symbol": sig_data.get("symbol"),
                "signal_type": sig_data.get("signal_type"),
                "confidence_score": sig_data.get("confidence_score"),
                "description": sig_data.get("description"),
                "is_bullish": sig_data.get("is_bullish"),
                "timestamp": datetime.utcnow().isoformat(),
            }))
        await r.close()
    except Exception as e:
        logger.warning("Redis publish failed", error=str(e))

    return {"signals_generated": new_count}


@celery_app.task(
    name="backend.tasks.scheduled.scan_chart_patterns_nifty50",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def scan_chart_patterns_nifty50(self):
    """
    Task 3: Scan all Nifty 50 stocks for candlestick patterns.
    Runs at 7:00 PM IST every weekday.
    """
    logger.info("Starting Nifty 50 chart pattern scan")
    try:
        return run_async(_async_scan_patterns())
    except Exception as exc:
        logger.error("Pattern scan failed", error=str(exc))
        raise self.retry(exc=exc)


async def _async_scan_patterns():
    """Async implementation of full Nifty 50 pattern scan."""
    from backend.agents.chart_patterns import ChartPatternAgent
    from backend.database import AsyncSessionLocal
    from backend.models import PatternHistory, Signal

    agent = ChartPatternAgent()
    patterns = await agent.scan_nifty50()

    async with AsyncSessionLocal() as session:
        for pat in patterns:
            # Store in pattern_history
            ph = PatternHistory(
                symbol=pat.get("symbol"),
                pattern_name=pat.get("pattern_name"),
                success_rate=pat.get("success_rate"),
                price_at_detection=pat.get("price"),
                confidence_score=pat.get("confidence_score"),
                raw_data=pat,
            )
            session.add(ph)

            # Also create a Signal for this pattern
            sig = Signal(
                symbol=pat.get("symbol"),
                signal_type="CHART_PATTERN",
                description=f"{pat.get('display_name', pat.get('pattern_name'))} detected on {pat.get('symbol')} at ₹{pat.get('price', 0):.2f}",
                confidence_score=float(pat.get("confidence_score", 50)),
                explanation=pat.get("explanation"),
                raw_data=pat,
                is_bullish=pat.get("is_bullish", True),
            )
            session.add(sig)

        await session.commit()

    logger.info("Pattern scan complete", patterns=len(patterns))
    return {"patterns_detected": len(patterns)}


@celery_app.task(
    name="backend.tasks.scheduled.update_embeddings",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def update_embeddings(self):
    """
    Task 4: Refresh ChromaDB with latest market signals.
    Runs at 7:30 PM IST every weekday.
    """
    logger.info("Starting ChromaDB embeddings update")
    try:
        return run_async(_async_update_embeddings())
    except Exception as exc:
        logger.error("Embeddings update failed", error=str(exc))
        raise self.retry(exc=exc)


async def _async_update_embeddings():
    """Async implementation of embeddings refresh."""
    from backend.database import AsyncSessionLocal
    from backend.models import Signal
    from backend.data.embeddings import store_market_signals
    from sqlalchemy import select
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=1)

    async with AsyncSessionLocal() as session:
        stmt = select(Signal).where(Signal.created_at >= cutoff)
        result = await session.execute(stmt)
        recent_signals = result.scalars().all()

    documents = [
        {
            "id": sig.id,
            "text": f"{sig.symbol}: {sig.description}",
            "metadata": {
                "symbol": sig.symbol,
                "signal_type": sig.signal_type,
                "confidence": sig.confidence_score,
            },
        }
        for sig in recent_signals
    ]

    if documents:
        await store_market_signals(documents)

    logger.info("Embeddings updated", count=len(documents))
    return {"updated_signals": len(documents)}
