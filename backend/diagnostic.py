#!/usr/bin/env python3
"""
Diagnostic utility to check data pipeline health.
Usage: python backend/diagnostic.py
"""

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/et_intelligence.db")


async def check_pipelines():
    """Run all diagnostic checks."""
    print("\n" + "=" * 80)
    print(" DATA PIPELINE DIAGNOSTIC REPORT")
    print("=" * 80 + "\n")

    # Test 1: NSE Bhavcopy
    print("[1] NSE Bhavcopy CSV Download")
    print("-" * 80)
    try:
        from backend.data.nse_fetcher import download_bhavcopy
        yesterday = date.today() - timedelta(days=1)
        while yesterday.weekday() >= 5:  # Skip weekends
            yesterday -= timedelta(days=1)

        df = await download_bhavcopy(yesterday)
        print(f"✓ Downloaded {len(df)} stocks for {yesterday.strftime('%Y-%m-%d')}")
        if len(df) > 0:
            print(f"  Sample: {df.iloc[0]['symbol']} | Close: ₹{df.iloc[0]['close']:.2f}")
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:100]}")

    # Test 2: SEBI Bulk Deals
    print("\n[2] SEBI Bulk/Block Deals")
    print("-" * 80)
    try:
        from backend.data.sebi_fetcher import fetch_bulk_deals
        to_date = date.today()
        from_date = to_date - timedelta(days=2)
        df = await fetch_bulk_deals(from_date, to_date)
        print(f"✓ Downloaded {len(df)} deals")
        if len(df) > 0:
            print(f"  Sample: {df.iloc[0]['symbol']} | Value: ₹{float(df.iloc[0]['value']):.2f}Cr")
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:100]}")

    # Test 3: yfinance Live Quotes
    print("\n[3] yfinance Live Quotes")
    print("-" * 80)
    try:
        from backend.data.nse_fetcher import get_live_quote
        quote = await get_live_quote("RELIANCE")
        if quote.get("price", 0) > 0:
            print(f"✓ RELIANCE = ₹{quote['price']:.2f} ({quote.get('change_pct', 0):+.2f}%)")
        else:
            print(f"✗ No price data (quote={quote})")
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:100]}")

    # Test 4: Database
    print("\n[4] SQLite Database")
    print("-" * 80)
    try:
        from backend.database import Base, get_db_async
        from backend.models import Signal

        # Try to query signals
        async with get_db_async() as session:
            signals = await session.execute(
                "SELECT COUNT(*) as count FROM signals"
            )
            count = signals.scalar()
            print(f"✓ Database connected | {count} signals stored")
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:100]}")

    # Test 5: Redis
    print("\n[5] Redis Connection")
    print("-" * 80)
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
        print(f"✓ Redis connected | Keys: {r.dbsize()}")
    except Exception as e:
        print(f"⚠ Redis not available (expected in dev): {str(e)[:80]}")

    # Test 6: TA-Lib
    print("\n[6] TA-Lib Technical Indicators")
    print("-" * 80)
    try:
        import talib
        print(f"✓ TA-Lib available | Version: {talib.__version__}")
    except ImportError:
        print(f"⚠ TA-Lib not installed (optional)")
    except Exception as e:
        print(f"⚠ TA-Lib error: {str(e)[:80]}")

    # Test 7: Transformers (FinBERT)
    print("\n[7] Transformers / FinBERT")
    print("-" * 80)
    try:
        import transformers
        print(f"✓ Transformers available | Version: {transformers.__version__}")
    except ImportError:
        print(f"✗ Transformers not installed")
    except Exception as e:
        print(f"✗ Error: {str(e)[:100]}")

    print("\n" + "=" * 80)
    print(" END OF DIAGNOSTIC REPORT")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(check_pipelines())
