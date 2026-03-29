"""
data/nse_fetcher.py — NSE Bhavcopy downloader, yfinance live quotes, historical OHLCV.
"""

import asyncio
import io
from datetime import date, datetime, timedelta
from typing import Optional
import httpx
import pandas as pd
import structlog
import yfinance as yf

logger = structlog.get_logger(__name__)

# Cache: symbol → (timestamp, data)
_quote_cache: dict = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes

# Semaphore to prevent thread pool exhaustion (max 10 parallel yfinance calls)
_fetch_semaphore = asyncio.Semaphore(10)


async def download_bhavcopy(trade_date: date) -> pd.DataFrame:
    """
    Download and parse NSE Bhavcopy CSV for a given trading date.
    Args:
        trade_date: The trading date to fetch data for.
    Returns:
        DataFrame with columns: symbol, open, high, low, close, volume, date
    """
    date_str = trade_date.strftime("%d%b%Y").upper()
    year = trade_date.strftime("%Y")
    month = trade_date.strftime("%b").upper()

    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{date_str}bhav.csv.zip"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.nseindia.com/",
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            # Parse zip file in memory
            import zipfile
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                with zf.open(csv_name) as f:
                    df = pd.read_csv(f)

            # Normalize columns
            df.columns = [c.strip().upper() for c in df.columns]
            df = df.rename(columns={
                "SYMBOL": "symbol",
                "OPEN": "open",
                "HIGH": "high",
                "LOW": "low",
                "CLOSE": "close",
                "TOTTRDQTY": "volume",
                "TIMESTAMP": "date",
            })

            df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
            df = df[["symbol", "open", "high", "low", "close", "volume", "date"]].dropna(subset=["close"])
            logger.info("Bhavcopy downloaded", date=str(trade_date), rows=len(df))
            return df

        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Bhavcopy download failed", attempt=attempt + 1, error=str(e), url=url)
            if attempt < 2:
                await asyncio.sleep(wait)

    logger.error("Bhavcopy download failed after 3 attempts", date=str(trade_date))
    
    # NEW: Recursive fallback to previous weekday if today fails (common on NSE)
    # The current local time is Friday 04:18 AM IST, so today's file doesn't exist yet.
    if trade_date >= date.today() - timedelta(days=2):
        prev_date = trade_date - timedelta(days=1)
        # Skip weekends
        while prev_date.weekday() >= 5:
            prev_date -= timedelta(days=1)
        logger.info("Retrying with previous trading date", date=str(prev_date))
        return await download_bhavcopy(prev_date)

    return pd.DataFrame()


async def get_historical_ohlcv(symbol: str, days: int = 365) -> pd.DataFrame:
    """
    Fetch historical OHLCV data from yfinance.
    """
    ticker_symbol = f"{symbol}.NS"
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    for attempt in range(3):
        try:
            df = await asyncio.to_thread(lambda: yf.Ticker(ticker_symbol).history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=True,
            ))

            if df.empty:
                logger.warning("No data from yfinance", symbol=symbol)
                return pd.DataFrame()

            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={"date": "date"})
            df["symbol"] = symbol

            cols = [c for c in ["date", "open", "high", "low", "close", "volume", "symbol"] if c in df.columns]
            df = df[cols]
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df.sort_values("date").reset_index(drop=True)

            logger.info("Historical OHLCV fetched", symbol=symbol, rows=len(df))
            return df

        except Exception as e:
            logger.warning("yfinance fetch failed", symbol=symbol, attempt=attempt + 1, error=str(e))
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

    return pd.DataFrame()


async def get_live_quote(symbol: str) -> dict:
    """
    Fetch real-time quote for a symbol with retry logic and NSE Bhavcopy fallback.
    """
    import time

    # Check cache
    if symbol in _quote_cache:
        cached_time, cached_data = _quote_cache[symbol]
        if time.time() - cached_time < _CACHE_TTL_SECONDS:
            return cached_data

    ticker_symbol = f"{symbol}.NS"

    for attempt in range(2):  # Reduced to 2 attempts since yfinance is clearly broken
        try:
            async with _fetch_semaphore:
                info = await asyncio.wait_for(
                    asyncio.to_thread(lambda: yf.Ticker(ticker_symbol).fast_info),
                    timeout=10.0
                )

                quote = {
                    "symbol": symbol,
                    "price": getattr(info, "last_price", 0) or 0,
                    "change": getattr(info, "regular_market_change", 0) or 0,
                    "change_pct": getattr(info, "regular_market_change_percent", 0) or 0,
                    "volume": getattr(info, "regular_market_volume", 0) or 0,
                    "high_52w": getattr(info, "year_high", 0) or 0,
                    "low_52w": getattr(info, "year_low", 0) or 0,
                    "market_cap": getattr(info, "market_cap", 0) or 0,
                }

                if quote["price"] > 0:
                    _quote_cache[symbol] = (time.time(), quote)
                    return quote

        except Exception as e:
            logger.debug("yfinance attempt failed", symbol=symbol, attempt=attempt + 1, error=str(e)[:50])
            if attempt < 1:
                await asyncio.sleep(1)

    # yfinance failed completely — fall back to NSE Bhavcopy
    logger.warning("yfinance failed, using NSE Bhavcopy fallback", symbol=symbol)
    try:
        bhavcopy_df = await download_bhavcopy(date.today())

        if bhavcopy_df.empty:
            bhavcopy_df = await download_bhavcopy(date.today() - timedelta(days=1))

        if not bhavcopy_df.empty:
            sym_data = bhavcopy_df[bhavcopy_df["symbol"] == symbol]
            if not sym_data.empty:
                row = sym_data.iloc[-1]
                change_pct = ((row["close"] - row["open"]) / row["open"] * 100) if row["open"] > 0 else 0
                quote = {
                    "symbol": symbol,
                    "price": float(row["close"]),
                    "change": float(row["close"] - row["open"]),
                    "change_pct": float(change_pct),
                    "volume": float(row["volume"]),
                    "high_52w": float(row["high"]),
                    "low_52w": float(row["low"]),
                    "market_cap": 0,
                }
                _quote_cache[symbol] = (time.time(), quote)
                return quote
    except Exception as e:
        logger.error("NSE Bhavcopy fallback failed", symbol=symbol, error=str(e)[:50])

    # Both failed — return zero
    return {"symbol": symbol, "price": 0, "change": 0, "change_pct": 0}


async def get_52week_data(symbol: str) -> dict:
    """Fetch 52-week data."""
    try:
        df = await get_historical_ohlcv(symbol, days=365)
        if df.empty:
            return {}

        high_52w = float(df["high"].max())
        low_52w = float(df["low"].min())
        current = float(df["close"].iloc[-1])

        return {
            "symbol": symbol,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "current_price": current,
            "distance_from_high_pct": round((current - high_52w) / high_52w * 100, 2),
            "distance_from_low_pct": round((current - low_52w) / low_52w * 100, 2),
        }
    except Exception as e:
        logger.error("52-week data failed", symbol=symbol, error=str(e))
        return {}


async def get_nifty_index_from_cached_bhavcopy() -> dict:
    """
    Compute Nifty 50 index from cached NSE Bhavcopy in SQLite database.
    Returns zero if no cached data available.
    """
    from backend.config import NIFTY50_SYMBOLS
    from backend.database import SessionLocal
    from backend.models import OHLCData
    import time

    db = None
    try:
        db = SessionLocal()
        #  Get latest Nifty 50 data from database
        latest_data = db.query(OHLCData).filter(
            OHLCData.symbol.in_(NIFTY50_SYMBOLS)
        ).order_by(OHLCData.date.desc()).all()

        if not latest_data:
            logger.warning("No cached Bhavcopy data in database")
            return {"price": 0, "change": 0, "change_pct": 0}

        # Get most recent date
        latest_date = latest_data[0].date
        today_data = [r for r in latest_data if r.date == latest_date]

        if len(today_data) < 20:
            logger.warning("Insufficient cached data", count=len(today_data))
            return {"price": 0, "change": 0, "change_pct": 0}

        closes = [float(r.close) for r in today_data if r.close and r.close > 0]
        opens = [float(r.open) for r in today_data if r.open and r.open > 0]

        if not closes or not opens:
            return {"price": 0, "change": 0, "change_pct": 0}

        avg_close = sum(closes) / len(closes)
        avg_open = sum(opens) / len(opens)
        change = avg_close - avg_open
        change_pct = (change / avg_open * 100) if avg_open > 0 else 0

        result = {
            "price": round(avg_close, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }

        _quote_cache["^NSEI"] = (time.time(), result)
        logger.info("Nifty computed from cache", price=avg_close)
        return result

    except Exception as e:
        logger.error("Failed to compute Nifty from cache", error=str(e)[:50])
        return {"price": 0, "change": 0, "change_pct": 0}
    finally:
        if db:
            db.close()


async def get_market_breadth_from_bhavcopy() -> dict:
    """
    Calculate market breadth (advances/declines) from NSE Bhavcopy.
    """
    from backend.config import NIFTY50_SYMBOLS

    try:
        bhavcopy_df = await download_bhavcopy(date.today())

        if bhavcopy_df.empty:
            bhavcopy_df = await download_bhavcopy(date.today() - timedelta(days=1))

        if bhavcopy_df.empty:
            return {"advances": 0, "declines": 0, "unchanged": 0}

        # Filter for Nifty 50
        nifty_data = bhavcopy_df[bhavcopy_df["symbol"].isin(NIFTY50_SYMBOLS)]

        advances = len(nifty_data[nifty_data["close"] > nifty_data["open"]])
        declines = len(nifty_data[nifty_data["close"] < nifty_data["open"]])
        unchanged = len(nifty_data[nifty_data["close"] == nifty_data["open"]])

        logger.info("Market breadth calculated", advances=advances, declines=declines, unchanged=unchanged)
        return {
            "advances": int(advances),
            "declines": int(declines),
            "unchanged": int(unchanged),
        }

    except Exception as e:
        logger.error("Market breadth calculation failed", error=str(e)[:50])
        return {"advances": 0, "declines": 0, "unchanged": 0}


async def get_sector_performance_from_bhavcopy() -> dict:
    """
    Calculate sector performance from NSE Bhavcopy.
    Returns average change_pct per sector.
    """
    from backend.config import SECTOR_SYMBOLS

    try:
        bhavcopy_df = await download_bhavcopy(date.today())

        if bhavcopy_df.empty:
            bhavcopy_df = await download_bhavcopy(date.today() - timedelta(days=1))

        if bhavcopy_df.empty:
            return {}

        sector_perf = {}

        for sector, symbols in SECTOR_SYMBOLS.items():
            sector_data = bhavcopy_df[bhavcopy_df["symbol"].isin(symbols)]

            if sector_data.empty:
                sector_perf[sector] = {
                    "avg_change_pct": 0.0,
                    "direction": "flat",
                    "stocks": [],
                }
                continue

            # Calculate change_pct for each stock
            sector_data_copy = sector_data.copy()
            sector_data_copy["change_pct"] = ((sector_data_copy["close"] - sector_data_copy["open"]) / sector_data_copy["open"] * 100).fillna(0)

            avg_change = float(sector_data_copy["change_pct"].mean())
            direction = "up" if avg_change > 0.5 else ("down" if avg_change < -0.5 else "flat")

            stocks = [
                {
                    "symbol": row["symbol"],
                    "change_pct": round(((row["close"] - row["open"]) / row["open"] * 100) if row["open"] > 0 else 0, 2),
                }
                for _, row in sector_data_copy.iterrows()
            ]

            sector_perf[sector] = {
                "avg_change_pct": round(avg_change, 2),
                "direction": direction,
                "stocks": stocks[:4],  # Top 4 stocks per sector
            }

        logger.info("Sector performance calculated from Bhavcopy", sectors=len(sector_perf))
        return sector_perf

    except Exception as e:
        logger.error("Sector performance calculation failed", error=str(e)[:50])
        return {}


async def get_nifty50_quotes() -> list[dict]:
    """Fetch live quotes for all Nifty 50 stocks, using NSE Bhavcopy as fallback."""
    from backend.config import NIFTY50_SYMBOLS
    try:
        # First, try yfinance
        tasks = [get_live_quote(sym) for sym in NIFTY50_SYMBOLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        quotes = [r for r in results if isinstance(r, dict) and r.get("price", 0) > 0]

        # If yfinance completely failed (0 quotes), fall back to NSE Bhavcopy
        if len(quotes) < 5:  # Too few quotes, probably yfinance is down
            logger.warning("yfinance returned insufficient data, using NSE Bhavcopy fallback", quotes_count=len(quotes))
            bhavcopy_df = await download_bhavcopy(date.today())

            if bhavcopy_df.empty:
                bhavcopy_df = await download_bhavcopy(date.today() - timedelta(days=1))

            if not bhavcopy_df.empty:
                # Convert Bhavcopy to quote format
                for symbol in NIFTY50_SYMBOLS:
                    if symbol not in [q["symbol"] for q in quotes]:
                        sym_data = bhavcopy_df[bhavcopy_df["symbol"] == symbol]
                        if not sym_data.empty:
                            row = sym_data.iloc[-1]
                            # Calculate change_pct from day's OHLC
                            change_pct = ((row["close"] - row["open"]) / row["open"] * 100) if row["open"] > 0 else 0
                            quotes.append({
                                "symbol": symbol,
                                "price": float(row["close"]),
                                "change": float(row["close"] - row["open"]),
                                "change_pct": float(change_pct),
                                "volume": float(row["volume"]),
                            })

        quotes.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        return quotes
    except Exception as e:
        logger.error("Nifty 50 quotes fetch failed", error=str(e))
        return []
