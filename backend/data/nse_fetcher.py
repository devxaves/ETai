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
    Fetch real-time quote for a symbol.
    """
    import time

    # Check cache
    if symbol in _quote_cache:
        cached_time, cached_data = _quote_cache[symbol]
        if time.time() - cached_time < _CACHE_TTL_SECONDS:
            return cached_data

    ticker_symbol = f"{symbol}.NS"

    try:
        async with _fetch_semaphore:
            # Crucial: Move Ticker creation to thread as it can do sync requests in __init__
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

            if quote["price"] == 0:
                history = await asyncio.wait_for(
                    asyncio.to_thread(lambda: yf.Ticker(ticker_symbol).history(period="1d")),
                    timeout=5.0
                )
                if not history.empty:
                    quote["price"] = history["Close"].iloc[-1]
                    quote["change_pct"] = ((history["Close"].iloc[-1] - history["Open"].iloc[0]) / history["Open"].iloc[0] * 100) if history["Open"].iloc[0] != 0 else 0

        _quote_cache[symbol] = (time.time(), quote)
        return quote

    except Exception as e:
        logger.warning("Live quote failed", symbol=symbol, error=str(e))
        return {"symbol": symbol, "price": 0, "change": 0, "change_pct": 0, "error": str(e)}


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


async def get_nifty50_quotes() -> list[dict]:
    """Fetch live quotes for all Nifty 50 stocks."""
    from backend.config import NIFTY50_SYMBOLS
    try:
        tasks = [get_live_quote(sym) for sym in NIFTY50_SYMBOLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        quotes = [r for r in results if isinstance(r, dict) and r.get("price")]
        quotes.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        return quotes
    except Exception as e:
        logger.error("Nifty 50 quotes fetch failed", error=str(e))
        return []
