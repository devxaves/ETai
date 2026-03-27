"""
agents/opportunity_radar.py — Agent 1: SEBI Bulk Deal Signal Detector.
Scans institutional buying patterns and cross-references with FinBERT sentiment.
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import List, Optional
import pandas as pd
import structlog

from backend.llm_router import llm_router
from backend.models import Signal

logger = structlog.get_logger(__name__)


class OpportunityRadarAgent:
    """
    Agent 1: Scans SEBI bulk/block deals and insider patterns to generate
    high-confidence trading signals for retail investors.
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self._finbert_pipeline = None

    def _get_finbert(self):
        """Lazy-load FinBERT sentiment pipeline."""
        if self._finbert_pipeline is None:
            from transformers import pipeline
            logger.info("Loading FinBERT model...")
            self._finbert_pipeline = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                device=-1,  # CPU
            )
            logger.info("FinBERT loaded")
        return self._finbert_pipeline

    async def scan_bulk_deals(self) -> List[dict]:
        """
        Scan last 30 days of SEBI bulk deals.
        Flags stocks with unusual institutional activity (quantity > 2x average).

        Returns:
            List of signal dicts with symbol, confidence, description, raw_data.
        """
        from backend.data.sebi_fetcher import get_recent_bulk_deals

        logger.info("Starting bulk deal scan")
        signals = []

        try:
            df = await get_recent_bulk_deals(days=30, db_session=self.db)
            if df.empty:
                logger.warning("No bulk deal data available")
                return []

            # Normalize symbol column
            if "symbol" not in df.columns:
                return []
            df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

            # Compute average quantity per symbol
            avg_qty = df.groupby("symbol")["quantity"].mean()
            # Use Timestamp correctly for comparison
            cutoff = pd.Timestamp(datetime.utcnow().date() - timedelta(days=7))
            recent_df = df[pd.to_datetime(df["date"]) >= cutoff] if "date" in df.columns else df

            for symbol, group in recent_df.groupby("symbol"):
                total_qty = group["quantity"].sum()
                avg = avg_qty.get(symbol, total_qty)

                if pd.isna(avg) or avg == 0:
                    continue

                # Flag if recent activity > 1.1x historical average (Demo mode)
                ratio = total_qty / avg
                if ratio < 1.1:
                    continue

                buy_deals = group[group.get("deal_type", pd.Series()) == "BUY"] if "deal_type" in group.columns else group
                sell_deals = group[group.get("deal_type", pd.Series()) == "SELL"] if "deal_type" in group.columns else pd.DataFrame()

                net_bias = "bullish" if len(buy_deals) >= len(sell_deals) else "bearish"
                confidence = min(95, 50 + ratio * 10)

                top_buyer = "Unknown"
                if "client_name" in group.columns and not group.empty:
                    top_buyer = group.iloc[0]["client_name"]

                description = (
                    f"Unusual institutional activity in {symbol}: "
                    f"₹{total_qty/1e7:.1f} Cr traded ({ratio:.1f}x average). "
                    f"Top participant: {top_buyer}. Bias: {net_bias.upper()}."
                )

                signals.append({
                    "symbol": symbol,
                    "signal_type": "BULK_DEAL",
                    "description": description,
                    "confidence_score": round(confidence, 1),
                    "is_bullish": net_bias == "bullish",
                    "raw_data": {
                        "total_quantity": float(total_qty),
                        "avg_quantity": float(avg),
                        "ratio": float(ratio),
                        "deals_count": len(group),
                        "top_buyer": top_buyer,
                    },
                })

            logger.info("Bulk deal scan complete", signals_found=len(signals))
            return signals

        except Exception as e:
            logger.error("Bulk deal scan failed", error=str(e))
            return []

    async def detect_insider_patterns(self) -> List[dict]:
        """
        Look for promoter buying patterns: same entity buying on 3+ consecutive days.
        Correlates with historical price moves to score signal strength.

        Returns:
            List of signal dicts.
        """
        from backend.data.sebi_fetcher import get_recent_bulk_deals

        logger.info("Detecting insider patterns")
        signals = []

        try:
            df = await get_recent_bulk_deals(days=30, db_session=self.db)
            if df.empty or "client_name" not in df.columns:
                return []

            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
            df = df.sort_values("date")

            # Group by (symbol, client_name) and look for consecutive buying
            for (symbol, client), group in df.groupby(["symbol", "client_name"]):
                buy_group = group[group.get("deal_type", "BUY") == "BUY"] if "deal_type" in group.columns else group
                if len(buy_group) < 3:
                    continue

                dates = sorted(buy_group["date"].dt.date.unique())
                consecutive = self._find_consecutive_dates(dates)

                if consecutive < 3:
                    continue

                total_qty = float(buy_group["quantity"].sum())
                avg_price = float(buy_group["price"].mean()) if "price" in buy_group.columns else 0

                confidence = min(92, 60 + consecutive * 8)
                description = (
                    f"Promoter/Institution '{client[:40]}' bought {symbol} on "
                    f"{consecutive} consecutive days — total {total_qty/1e5:.1f}L shares "
                    f"@ avg ₹{avg_price:.0f}. Historically, sustained promoter buying "
                    f"precedes significant price appreciation."
                )

                signals.append({
                    "symbol": symbol,
                    "signal_type": "INSIDER_PATTERN",
                    "description": description,
                    "confidence_score": round(confidence, 1),
                    "is_bullish": True,
                    "raw_data": {
                        "client_name": client,
                        "consecutive_days": consecutive,
                        "total_quantity": total_qty,
                        "avg_price": avg_price,
                    },
                })

            logger.info("Insider pattern detection complete", patterns=len(signals))
            return signals

        except Exception as e:
            logger.error("Insider pattern detection failed", error=str(e))
            return []

    def _find_consecutive_dates(self, dates: list) -> int:
        """Find the maximum streak of consecutive trading dates."""
        if not dates:
            return 0

        max_streak = 1
        current_streak = 1

        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i - 1]).days
            if diff <= 3:  # Allow for weekends
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1

        return max_streak

    async def run_finbert_sentiment(self, texts: List[str]) -> List[dict]:
        """
        Run FinBERT sentiment analysis on a list of texts.

        Args:
            texts: List of financial text snippets.

        Returns:
            List of {label, score} sentiment dicts.
        """
        try:
            pipeline_fn = self._get_finbert()
            results = await asyncio.to_thread(pipeline_fn, texts, truncation=True, max_length=512)
            return results
        except Exception as e:
            logger.warning("FinBERT failed", error=str(e))
            return [{"label": "neutral", "score": 0.5} for _ in texts]

    async def explain_signal(self, signal: dict) -> str:
        """
        Generate a plain-English explanation for a signal using the LLM router.

        Args:
            signal: Signal dict with symbol, description, confidence_score, raw_data.

        Returns:
            LLM-generated explanation string.
        """
        system = (
            "You are an expert Indian stock market analyst explaining investment signals "
            "to retail investors in plain, simple English. Be specific, actionable, and honest about risks. "
            "Never guarantee returns. Always mention relevant risks. Keep your response under 200 words."
        )

        raw = signal.get("raw_data", {})
        prompt = f"""
A trading signal has been detected for {signal.get('symbol', 'Unknown')}:

Signal Type: {signal.get('signal_type', '')}
Description: {signal.get('description', '')}
Confidence Score: {signal.get('confidence_score', 0):.0f}/100
Direction: {'BULLISH 🟢' if signal.get('is_bullish') else 'BEARISH 🔴'}
Additional Data: {raw}

Please explain:
1. What happened: What does this signal mean in simple terms?
2. Why it matters: Why should a retail investor pay attention?
3. Historical context: What do similar patterns usually lead to?
4. What to watch: Key price levels or catalysts to track.
5. Key risks: What could go wrong? Why might this signal fail?

Write as if you're explaining to a first-time investor who understands basic stock concepts.
"""
        try:
            explanation = await llm_router.complete(prompt, system=system, max_tokens=400)
            return explanation
        except Exception as e:
            logger.error("Signal explanation failed", error=str(e))
            return f"Signal detected for {signal.get('symbol')}: {signal.get('description')}"

    async def run_full_scan(self) -> List[dict]:
        """
        Run a complete opportunity scan: bulk deals + insider patterns.
        Generates LLM explanations for top signals.

        Returns:
            Combined list of all signals, sorted by confidence descending.
        """
        logger.info("Running full opportunity radar scan")

        # FIX: Avoid concurrent DB operations on the same session
        # Run them sequentially instead of asyncio.gather
        try:
            bulk_signals = await self.scan_bulk_deals()
            insider_signals = await self.detect_insider_patterns()
        except Exception as e:
            logger.error("Radar scan parts failed", error=str(e))
            bulk_signals, insider_signals = [], []

        all_signals = []
        for sig_list in [bulk_signals, insider_signals]:
            if isinstance(sig_list, list):
                all_signals.extend(sig_list)

        # Sort by confidence and enrich top 5 with LLM explanations
        all_signals.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)

        top_signals = all_signals[:5]
        explanation_tasks = [self.explain_signal(sig) for sig in top_signals]
        explanations = await asyncio.gather(*explanation_tasks, return_exceptions=True)

        for sig, exp in zip(top_signals, explanations):
            sig["explanation"] = exp if isinstance(exp, str) else "Explanation unavailable."

        logger.info("Full scan complete", total_signals=len(all_signals))
        return all_signals
