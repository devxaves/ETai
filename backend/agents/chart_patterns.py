"""
agents/chart_patterns.py — Agent 2: TA-Lib Candlestick Pattern Detector + Backtester.
Scans all Nifty 50 symbols, detects chart patterns, backtests success rates.
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
import structlog

from backend.llm_router import llm_router
from backend.config import NIFTY50_SYMBOLS

logger = structlog.get_logger(__name__)

# All TA-Lib CDL function names to scan for
CDL_PATTERNS = [
    "CDL2CROWS", "CDL3BLACKCROWS", "CDL3INSIDE", "CDL3LINESTRIKE", "CDL3OUTSIDE",
    "CDL3STARSINSOUTH", "CDL3WHITESOLDIERS", "CDLABANDONEDBABY", "CDLADVANCEBLOCK",
    "CDLBELTHOLD", "CDLBREAKAWAY", "CDLCLOSINGMARUBOZU", "CDLCONCEALBABYSWALL",
    "CDLCOUNTERATTACK", "CDLDARKCLOUDCOVER", "CDLDOJI", "CDLDOJISTAR",
    "CDLDRAGONFLYDOJI", "CDLENGULFING", "CDLEVENINGDOJISTAR", "CDLEVENINGSTAR",
    "CDLGAPSIDESIDEWHITE", "CDLGRAVESTONEDOJI", "CDLHAMMER", "CDLHANGINGMAN",
    "CDLHARAMI", "CDLHARAMICROSS", "CDLHIGHWAVE", "CDLHIKKAKE", "CDLHIKKAKEMOD",
    "CDLHOMINGPIGEON", "CDLIDENTICAL3CROWS", "CDLINNECK", "CDLINVERTEDHAMMER",
    "CDLKICKING", "CDLKICKINGBYLENGTH", "CDLLADDERBOTTOM", "CDLLONGLEGGEDDOJI",
    "CDLLONGLINE", "CDLMARUBOZU", "CDLMATCHINGLOW", "CDLMATHOLD", "CDLMORNINGDOJISTAR",
    "CDLMORNINGSTAR", "CDLONNECK", "CDLPIERCING", "CDLRICKSHAWMAN",
    "CDLRISEFALL3METHODS", "CDLSEPARATINGLINES", "CDLSHOOTINGSTAR", "CDLSHORTLINE",
    "CDLSPINNINGTOP", "CDLSTALLEDPATTERN", "CDLSTICKSANDWICH", "CDLTAKURI",
    "CDLTASUKIGAP", "CDLTHRUSTING", "CDLTRISTAR", "CDLUNIQUE3RIVER", "CDLUPSIDEGAP2CROWS",
    "CDLXSIDEGAP3METHODS",
]

# Human-readable pattern names
PATTERN_LABELS = {
    "CDLDOJI": "Doji", "CDLHAMMER": "Hammer", "CDLENGULFING": "Engulfing",
    "CDLMORNINGSTAR": "Morning Star", "CDLEVENINGSTAR": "Evening Star",
    "CDLSHOOTINGSTAR": "Shooting Star", "CDLINVERTEDHAMMER": "Inverted Hammer",
    "CDLHARAMI": "Harami", "CDLPIERCING": "Piercing Line",
    "CDLDARKCLOUDCOVER": "Dark Cloud Cover", "CDLMARUBOZU": "Marubozu",
    "CDL3WHITESOLDIERS": "Three White Soldiers", "CDL3BLACKCROWS": "Three Black Crows",
    "CDLMORNINGDOJISTAR": "Morning Doji Star", "CDLEVENINGDOJISTAR": "Evening Doji Star",
    "CDLDRAGONFLYDOJI": "Dragonfly Doji", "CDLGRAVESTONEDOJI": "Gravestone Doji",
    "CDLHANGINGMAN": "Hanging Man", "CDLSPINNINGTOP": "Spinning Top",
}


class PatternDetection:
    """Represents a single detected chart pattern."""

    def __init__(
        self,
        symbol: str,
        pattern_name: str,
        signal_value: int,
        price: float,
        date: date,
        rsi: Optional[float] = None,
        macd: Optional[float] = None,
        bb_position: Optional[str] = None,
        success_rate: Optional[float] = None,
        confidence_score: float = 50.0,
    ):
        self.symbol = symbol
        self.pattern_name = pattern_name
        self.display_name = PATTERN_LABELS.get(pattern_name, pattern_name)
        self.signal_value = signal_value  # +100 bullish, -100 bearish
        self.is_bullish = signal_value > 0
        self.price = price
        self.date = date
        self.rsi = rsi
        self.macd = macd
        self.bb_position = bb_position
        self.success_rate = success_rate
        self.confidence_score = confidence_score
        self.explanation: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "pattern_name": self.pattern_name,
            "display_name": self.display_name,
            "signal_value": self.signal_value,
            "is_bullish": self.is_bullish,
            "price": self.price,
            "date": str(self.date),
            "rsi": self.rsi,
            "macd": self.macd,
            "bb_position": self.bb_position,
            "success_rate": self.success_rate,
            "confidence_score": self.confidence_score,
            "explanation": self.explanation,
        }


class ChartPatternAgent:
    """
    Agent 2: Detects candlestick patterns using TA-Lib, backtests them
    on historical data, and generates LLM explanations for retail investors.
    """

    async def scan_symbol(self, symbol: str) -> List[PatternDetection]:
        """
        Scan a single symbol for all candlestick patterns + technical indicators.

        Args:
            symbol: NSE symbol (e.g. "RELIANCE")

        Returns:
            List of detected PatternDetection objects.
        """
        from backend.data.nse_fetcher import get_historical_ohlcv

        try:
            df = await get_historical_ohlcv(symbol, days=200)
            if df.empty or len(df) < 50:
                logger.warning("Insufficient data for pattern scan", symbol=symbol)
                return []

            # Ensure sorted by date
            df = df.sort_values("date").reset_index(drop=True)

            open_arr = df["open"].values.astype(float)
            high_arr = df["high"].values.astype(float)
            low_arr = df["low"].values.astype(float)
            close_arr = df["close"].values.astype(float)

            # Calculate indicators
            rsi = self._calculate_rsi(close_arr)
            macd, macd_signal = self._calculate_macd(close_arr)
            bb_upper, bb_lower = self._calculate_bollinger(close_arr)

            last_close = float(close_arr[-1])
            last_rsi = float(rsi[-1]) if len(rsi) > 0 else None
            last_macd = float(macd[-1]) if len(macd) > 0 else None
            bb_pos = self._get_bb_position(last_close, float(bb_upper[-1]), float(bb_lower[-1])) if len(bb_upper) > 0 else "middle"
            last_date = df["date"].iloc[-1]

            detected = []

            # Try TA-Lib pattern detection
            try:
                import talib
                for pattern_fn_name in CDL_PATTERNS:
                    try:
                        fn = getattr(talib, pattern_fn_name)
                        result = fn(open_arr, high_arr, low_arr, close_arr)
                        last_val = int(result[-1])
                        if last_val != 0:
                            confidence = self._compute_confidence(last_val, last_rsi, last_macd)
                            detection = PatternDetection(
                                symbol=symbol,
                                pattern_name=pattern_fn_name,
                                signal_value=last_val,
                                price=last_close,
                                date=last_date,
                                rsi=last_rsi,
                                macd=last_macd,
                                bb_position=bb_pos,
                                confidence_score=confidence,
                            )
                            detected.append(detection)
                    except Exception:
                        continue
            except ImportError:
                # TA-Lib not available — use base indicator fallback
                detected.extend(
                    self._base_indicator_signals(symbol, df, last_close, last_date, last_rsi, last_macd, bb_pos)
                )

            # Sort by confidence
            detected.sort(key=lambda x: x.confidence_score, reverse=True)
            logger.info("Pattern scan complete", symbol=symbol, patterns=len(detected))
            return detected

        except Exception as e:
            logger.error("Symbol scan failed", symbol=symbol, error=str(e))
            return []

    def _base_indicator_signals(self, symbol, df, last_close, last_date, rsi, macd, bb_pos) -> List[PatternDetection]:
        """Fallback signal detection when TA-Lib is unavailable, using base indicators."""
        detected = []
        try:
            # RSI-based signals
            if rsi is not None:
                if rsi < 30:
                    detected.append(PatternDetection(
                        symbol=symbol, pattern_name="RSI_OVERSOLD", signal_value=100,
                        price=last_close, date=last_date, rsi=rsi, macd=macd,
                        bb_position=bb_pos, confidence_score=70.0
                    ))
                elif rsi > 70:
                    detected.append(PatternDetection(
                        symbol=symbol, pattern_name="RSI_OVERBOUGHT", signal_value=-100,
                        price=last_close, date=last_date, rsi=rsi, macd=macd,
                        bb_position=bb_pos, confidence_score=65.0
                    ))

            # MACD sign
            if macd is not None:
                if macd > 0:
                    detected.append(PatternDetection(
                        symbol=symbol, pattern_name="MACD_BULLISH", signal_value=100,
                        price=last_close, date=last_date, rsi=rsi, macd=macd,
                        bb_position=bb_pos, confidence_score=60.0
                    ))
                else:
                    detected.append(PatternDetection(
                        symbol=symbol, pattern_name="MACD_BEARISH", signal_value=-100,
                        price=last_close, date=last_date, rsi=rsi, macd=macd,
                        bb_position=bb_pos, confidence_score=55.0
                    ))
        except Exception as e:
            logger.warning("Base signal fallback failed", symbol=symbol, error=str(e))
        return detected

    def _calculate_rsi(self, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI using pure pandas."""
        try:
            delta = pd.Series(close).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50).values
        except Exception:
            return np.full(len(close), 50)

    def _calculate_macd(self, close: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate MACD using pure pandas."""
        try:
            s = pd.Series(close)
            ema12 = s.ewm(span=12, adjust=False).mean()
            ema26 = s.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            return macd.values, signal.values
        except Exception:
            return np.zeros(len(close)), np.zeros(len(close))

    def _calculate_bollinger(self, close: np.ndarray, period: int = 20, std: float = 2.0) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands."""
        s = pd.Series(close)
        rolling_mean = s.rolling(period).mean()
        rolling_std = s.rolling(period).std()
        upper = (rolling_mean + std * rolling_std).fillna(close[-1]).values
        lower = (rolling_mean - std * rolling_std).fillna(close[-1]).values
        return upper, lower

    def _get_bb_position(self, price: float, upper: float, lower: float) -> str:
        """Classify price position within Bollinger Bands."""
        if price >= upper:
            return "upper"
        elif price <= lower:
            return "lower"
        return "middle"

    def _compute_confidence(self, signal_val: int, rsi: Optional[float], macd: Optional[float]) -> float:
        """Compute a confidence score for a pattern detection."""
        base = 55.0
        if rsi is not None:
            if signal_val > 0 and rsi < 50:
                base += 10
            elif signal_val < 0 and rsi > 50:
                base += 10
        if macd is not None:
            if signal_val > 0 and macd > 0:
                base += 8
            elif signal_val < 0 and macd < 0:
                base += 8
        return min(95.0, base)

    async def backtest_pattern(self, symbol: str, pattern_name: str) -> float:
        """
        Backtest a pattern on 5 years of historical data.
        Counts occurrences where price was >5% higher within 10 trading days.

        Args:
            symbol: NSE symbol.
            pattern_name: TA-Lib CDL function name.

        Returns:
            Success rate as a percentage (0-100).
        """
        from backend.data.nse_fetcher import get_historical_ohlcv

        try:
            df = await get_historical_ohlcv(symbol, days=1825)  # 5 years
            if df.empty or len(df) < 100:
                return 50.0

            df = df.sort_values("date").reset_index(drop=True)
            open_arr = df["open"].values.astype(float)
            high_arr = df["high"].values.astype(float)
            low_arr = df["low"].values.astype(float)
            close_arr = df["close"].values.astype(float)

            try:
                import talib
                fn = getattr(talib, pattern_name, None)
                if fn is None:
                    return 50.0
                signals = fn(open_arr, high_arr, low_arr, close_arr)
            except ImportError:
                return 50.0

            total = 0
            wins = 0

            for i in range(len(signals) - 10):
                if signals[i] != 0:
                    entry_price = close_arr[i]
                    is_bullish = signals[i] > 0
                    future_prices = close_arr[i + 1: i + 11]

                    if len(future_prices) == 0:
                        continue

                    max_future = np.max(future_prices)
                    min_future = np.min(future_prices)

                    total += 1
                    if is_bullish and max_future > entry_price * 1.05:
                        wins += 1
                    elif not is_bullish and min_future < entry_price * 0.95:
                        wins += 1

            success_rate = (wins / total * 100) if total > 0 else 50.0
            logger.info("Backtest complete", symbol=symbol, pattern=pattern_name, rate=success_rate, total=total)
            return round(success_rate, 1)

        except Exception as e:
            logger.error("Backtest failed", symbol=symbol, pattern=pattern_name, error=str(e))
            return 50.0

    async def explain_pattern(self, symbol: str, pattern: PatternDetection) -> str:
        """
        Generate a retail-investor-friendly explanation of a detected pattern.

        Args:
            symbol: NSE symbol.
            pattern: PatternDetection object.

        Returns:
            LLM-generated explanation string.
        """
        system = (
            "You are a senior technical analyst explaining chart patterns to retail Indian investors. "
            "Keep explanations in simple English, under 200 words. "
            "Always mention: what the pattern is, why the stock might move, price targets, key risks. "
            "Never guarantee returns."
        )

        success_str = f"{pattern.success_rate:.0f}%" if pattern.success_rate else "not yet computed"
        rsi_str = f"{pattern.rsi:.1f}" if pattern.rsi else "N/A"
        macd_str = f"{pattern.macd:.2f}" if pattern.macd else "N/A"

        prompt = f"""
Stock {symbol} showed a **{pattern.display_name}** candlestick pattern today at price ₹{pattern.price:.2f}.

Technical context:
- RSI: {rsi_str} {'(oversold region)' if pattern.rsi and pattern.rsi < 30 else '(overbought region)' if pattern.rsi and pattern.rsi > 70 else '(neutral zone)'}
- MACD: {macd_str}
- Bollinger Band position: {pattern.bb_position or 'middle'}
- Pattern direction: {'BULLISH 🟢' if pattern.is_bullish else 'BEARISH 🔴'}
- Historical success rate for this pattern on {symbol}: {success_str}

Please explain this to a retail Indian investor:
1. What is a {pattern.display_name} and what does it signal?
2. Why is this significant at the current price level?
3. What price targets should the investor watch?
4. What are the key risks if the pattern fails?
"""
        try:
            return await llm_router.complete(prompt, system=system, max_tokens=350)
        except Exception as e:
            logger.error("Pattern explanation failed", symbol=symbol, error=str(e))
            return f"{pattern.display_name} detected on {symbol} at ₹{pattern.price:.2f}. RSI: {rsi_str}. This is a {'bullish' if pattern.is_bullish else 'bearish'} signal."

    async def scan_nifty50(self) -> List[dict]:
        """
        Scan all 50 Nifty stocks in parallel for candlestick patterns.
        Returns top 10 sorted by confidence score.

        Returns:
            List of top pattern detection dicts.
        """
        logger.info("Starting Nifty 50 full scan")

        tasks = [self.scan_symbol(sym) for sym in NIFTY50_SYMBOLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_patterns = []
        for result in results:
            if isinstance(result, list):
                all_patterns.extend(result)

        all_patterns.sort(key=lambda x: x.confidence_score, reverse=True)
        top10 = all_patterns[:10]

        # Enrich top patterns with LLM explanations
        explanation_tasks = [
            self.explain_pattern(p.symbol, p) for p in top10
        ]
        explanations = await asyncio.gather(*explanation_tasks, return_exceptions=True)
        for p, exp in zip(top10, explanations):
            p.explanation = exp if isinstance(exp, str) else None

        logger.info("Nifty 50 scan complete", total_patterns=len(all_patterns), top10=len(top10))
        return [p.to_dict() for p in top10]

    async def get_chart_data(self, symbol: str, days: int = 60) -> List[dict]:
        """
        Get OHLCV data formatted for the frontend chart renderer.

        Args:
            symbol: NSE symbol.
            days: Number of days of history.

        Returns:
            List of OHLCV dicts with time (unix timestamp).
        """
        from backend.data.nse_fetcher import get_historical_ohlcv

        df = await get_historical_ohlcv(symbol, days=days)
        if df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            try:
                dt = row["date"]
                if hasattr(dt, "timestamp"):
                    ts = int(dt.timestamp()) if hasattr(dt, "hour") else int(pd.Timestamp(dt).timestamp())
                else:
                    ts = int(pd.Timestamp(str(dt)).timestamp())
                result.append({
                    "time": ts,
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": int(row.get("volume", 0) or 0),
                })
            except Exception:
                continue

        return result
