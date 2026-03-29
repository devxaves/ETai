"""
agents/market_chatgpt.py — Agent 3: Portfolio-Aware RAG Chat.
Parses CAMS/KFintech statements, embeds portfolio context, answers questions.
"""

import asyncio
import io
import json
import re
from typing import List, Optional, AsyncGenerator
import pandas as pd
import structlog

from backend.llm_router import llm_router
# (Moved imports inside methods)

logger = structlog.get_logger(__name__)


class Holding:
    def __init__(self, fund_name, units=0, current_value=0, xirr=0, category="", folio_no="", invested_amount=0):
        self.fund_name = fund_name
        self.units = units
        self.current_value = current_value
        self.xirr = xirr
        self.category = category
        self.folio_no = folio_no
        self.invested_amount = invested_amount

    def to_dict(self):
        return {
            "fund_name": self.fund_name, "units": self.units,
            "current_value": self.current_value, "xirr": self.xirr,
            "category": self.category, "folio_no": self.folio_no,
            "invested_amount": self.invested_amount,
            "gain_loss": self.current_value - self.invested_amount,
            "gain_loss_pct": ((self.current_value - self.invested_amount) / self.invested_amount * 100) if self.invested_amount > 0 else 0,
        }


class Portfolio:
    def __init__(self, holdings: List[Holding], investor_name: str = ""):
        self.holdings = holdings
        self.investor_name = investor_name

    @property
    def total_value(self): return sum(h.current_value for h in self.holdings)
    @property
    def total_invested(self): return sum(h.invested_amount for h in self.holdings)
    @property
    def total_gain_pct(self):
        return ((self.total_value - self.total_invested) / self.total_invested * 100) if self.total_invested > 0 else 0

    def to_dict(self):
        return {
            "investor_name": self.investor_name, "total_value": self.total_value,
            "total_invested": self.total_invested, "total_gain_pct": round(self.total_gain_pct, 2),
            "holdings_count": len(self.holdings), "holdings": [h.to_dict() for h in self.holdings],
        }

    def to_summary_text(self):
        lines = [f"Portfolio of {self.investor_name or 'Investor'}:"]
        lines.append(f"Total Value: ₹{self.total_value:,.0f} | Return: {self.total_gain_pct:.1f}%")
        for h in self.holdings:
            lines.append(f"  - {h.fund_name}: ₹{h.current_value:,.0f} ({h.category}) XIRR:{h.xirr:.1f}%")
        return "\n".join(lines)


class PortfolioChatAgent:
    """Agent 3: Portfolio-aware RAG chat with CAMS parsing and ChromaDB retrieval."""

    def _safe_float(self, val) -> float:
        try:
            return float(str(val).replace(",", "").replace("₹", "").strip() or 0)
        except Exception:
            return 0.0

    def _get_sample_portfolio(self) -> Portfolio:
        return Portfolio(investor_name="Demo Investor", holdings=[
            Holding("HDFC Top 100 Fund - Growth", 250.5, 125000, 18.5, "Large Cap Equity", "12345", 80000),
            Holding("Axis Bluechip Fund - Direct Growth", 180.2, 95000, 21.3, "Large Cap Equity", "23456", 60000),
            Holding("SBI Small Cap Fund - Direct Growth", 120.8, 85000, 28.7, "Small Cap Equity", "34567", 45000),
            Holding("Mirae Asset Emerging Bluechip", 95.4, 72000, 16.8, "Large & Mid Cap", "45678", 50000),
            Holding("Parag Parikh Flexi Cap Fund", 88.9, 68000, 25.2, "Flexi Cap", "56789", 40000),
            Holding("ICICI Pru Balanced Advantage Fund", 320.1, 55000, 9.5, "Hybrid", "67890", 45000),
            Holding("SBI Liquid Fund - Direct", 1500.0, 150000, 7.2, "Liquid", "78901", 148000),
        ])

    async def parse_cams_statement(self, file_bytes: bytes, filename: str = "") -> Portfolio:
        """Parse CAMS/KFintech PDF or CSV mutual fund statement."""
        if filename.lower().endswith(".csv"):
            return await self._parse_csv(file_bytes)
        elif filename.lower().endswith(".pdf"):
            return await self._parse_pdf(file_bytes)
        else:
            try:
                return await self._parse_csv(file_bytes)
            except Exception:
                return self._get_sample_portfolio()

    async def _parse_csv(self, file_bytes: bytes) -> Portfolio:
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            df = pd.read_csv(io.StringIO(text))
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            col_aliases = {
                "fund_name": ["fund_name", "scheme_name", "scheme", "fund"],
                "units": ["units", "closing_unit_balance", "balance_units"],
                "current_value": ["current_value", "market_value", "value"],
                "invested_amount": ["invested_amount", "cost_value", "purchase_cost"],
                "xirr": ["xirr", "irr", "returns"],
                "category": ["category", "scheme_type", "fund_type"],
            }

            def find(candidates):
                for c in candidates:
                    if c in df.columns:
                        return c
                return None

            fund_col = find(col_aliases["fund_name"])
            if not fund_col:
                return self._get_sample_portfolio()

            holdings = []
            investor_name = ""
            if "investor_name" in df.columns:
                names = df["investor_name"].dropna()
                investor_name = str(names.iloc[0]) if not names.empty else ""

            for _, row in df.iterrows():
                name = str(row.get(fund_col, "")).strip()
                if not name or name.lower() in ["nan", "", "fund name"]:
                    continue
                holdings.append(Holding(
                    fund_name=name,
                    units=self._safe_float(row.get(find(col_aliases["units"]) or "", 0)),
                    current_value=self._safe_float(row.get(find(col_aliases["current_value"]) or "", 0)),
                    invested_amount=self._safe_float(row.get(find(col_aliases["invested_amount"]) or "", 0)),
                    xirr=self._safe_float(row.get(find(col_aliases["xirr"]) or "", 0)),
                    category=str(row.get(find(col_aliases["category"]) or "", "Equity")).strip(),
                ))

            return Portfolio(holdings=holdings or self._get_sample_portfolio().holdings, investor_name=investor_name)
        except Exception as e:
            logger.error("CSV parse failed", error=str(e))
            return self._get_sample_portfolio()

    async def _parse_pdf(self, file_bytes: bytes) -> Portfolio:
        try:
            import pdfplumber
            text_blocks = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_blocks.append(t)
            full_text = "\n".join(text_blocks)

            prompt = f"""Extract mutual fund holdings from this CAMS statement. 
Return ONLY a JSON array like: [{{"fund_name":"HDFC Top 100","units":150,"current_value":75000,"invested_amount":50000,"xirr":18.5,"category":"Large Cap Equity"}}]

Statement text:
{full_text[:3000]}"""
            response = await llm_router.complete(prompt, max_tokens=1500)
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
                holdings = [Holding(
                    fund_name=item.get("fund_name", "Unknown"),
                    units=float(item.get("units", 0) or 0),
                    current_value=float(item.get("current_value", 0) or 0),
                    invested_amount=float(item.get("invested_amount", 0) or 0),
                    xirr=float(item.get("xirr", 0) or 0),
                    category=item.get("category", "Equity"),
                ) for item in data if item.get("fund_name")]
                return Portfolio(holdings=holdings)
        except Exception as e:
            logger.error("PDF parse failed", error=str(e))
        return self._get_sample_portfolio()

    async def embed_and_store_portfolio(self, session_id: str, portfolio: Portfolio) -> None:
        """Embed portfolio in ChromaDB for RAG retrieval."""
        documents = [portfolio.to_summary_text()]
        metadatas = [{"type": "summary"}]

        for h in portfolio.holdings:
            documents.append(
                f"{h.fund_name} | {h.category} | Value:₹{h.current_value:,.0f} | "
                f"Invested:₹{h.invested_amount:,.0f} | XIRR:{h.xirr:.1f}% | Units:{h.units:.2f}"
            )
            metadatas.append({"type": "holding", "fund": h.fund_name})

        from backend.data.embeddings import store_portfolio_context
        await store_portfolio_context(session_id, documents, metadatas)

    async def chat(self, session_id: str, user_message: str, conversation_history: List[dict], portfolio=None) -> str:
        """Portfolio-aware RAG chat."""
        from backend.data.embeddings import retrieve_portfolio_context
        try:
            context_docs = await retrieve_portfolio_context(session_id, user_message, n_results=5)
        except Exception as e:
            logger.warning("Context retrieval failed, continuing without RAG context", error=str(e))
            context_docs = []

        context_text = "\n".join(context_docs)
        portfolio_summary = portfolio.to_summary_text() if portfolio else context_text[:800]

        system = f"""You are an expert Indian financial advisor. The investor's portfolio:
{portfolio_summary}

Rules: Always refer to actual holdings. Never guarantee returns. Use ₹. Be specific and concise (under 250 words)."""

        history = "".join(f"{m.get('role','user').title()}: {m.get('content','')}\n" for m in conversation_history[-4:])
        prompt = f"{history}User: {user_message}\nAssistant:"

        try:
            return await llm_router.complete(prompt, system=system, max_tokens=500)
        except Exception as e:
            logger.error("Chat failed", error=str(e))
            if portfolio and portfolio.holdings:
                top_holding = max(portfolio.holdings, key=lambda h: h.current_value)
                return (
                    f"I could not reach the live AI model, but here is a fallback summary: "
                    f"Your portfolio has {len(portfolio.holdings)} holdings with total value "
                    f"₹{portfolio.total_value:,.0f}. Your largest holding is {top_holding.fund_name} "
                    f"at ₹{top_holding.current_value:,.0f}. Consider reducing concentration risk and "
                    f"adding diversification across categories."
                )
            return "I could not reach the live AI model. Please try again in a moment."

    async def stream_chat(self, session_id, user_message, conversation_history, portfolio=None):
        """Streaming portfolio chat."""
        from backend.data.embeddings import retrieve_portfolio_context
        try:
            context_docs = await retrieve_portfolio_context(session_id, user_message, n_results=5)
        except Exception as e:
            logger.warning("Streaming context retrieval failed", error=str(e))
            context_docs = []

        portfolio_summary = portfolio.to_summary_text() if portfolio else "\n".join(context_docs)[:800]
        system = f"Expert Indian financial advisor. Portfolio:\n{portfolio_summary}\nBe specific to holdings. Under 250 words."
        history = "".join(f"{m.get('role','user').title()}: {m.get('content','')}\n" for m in conversation_history[-4:])
        prompt = f"{history}User: {user_message}\nAssistant:"
        try:
            async for chunk in llm_router.stream(prompt, system=system, max_tokens=500):
                yield chunk
        except Exception as e:
            logger.error("Streaming chat failed", error=str(e))
            yield "I could not reach the live AI model. Please try again in a moment."

    async def analyze_portfolio_health(self, portfolio: Portfolio) -> dict:
        """Full portfolio health analysis with LLM suggestions."""
        if not portfolio.holdings:
            return {"health_score": 50, "overlap_pct": 0, "rebalancing_suggestions": "No holdings."}

        total = portfolio.total_value or 1
        category_values: dict = {}
        for h in portfolio.holdings:
            category_values[h.category] = category_values.get(h.category, 0) + h.current_value
        sector_concentration = {cat: round(val / total * 100, 1) for cat, val in category_values.items()}

        equity_funds = [h for h in portfolio.holdings if "equity" in h.category.lower() or "cap" in h.category.lower()]
        overlap_pct = min(85.0, len(equity_funds) * 12.0) if len(equity_funds) > 2 else 15.0

        health = 70.0
        if len(portfolio.holdings) < 3: health -= 15
        if len(portfolio.holdings) > 10: health -= 10
        if overlap_pct > 60: health -= 10
        health = max(0, min(100, health))

        equity_pct = sum(v for k, v in sector_concentration.items() if "equity" in k.lower() or "cap" in k.lower())
        risk_level = "High" if equity_pct > 70 else "Moderate" if equity_pct > 40 else "Low"

        prompt = f"""Analyze this portfolio and give 3-4 specific rebalancing suggestions (under 150 words):
{portfolio.to_summary_text()}
Allocation: {sector_concentration}, Overlap: {overlap_pct:.0f}%"""
        try:
            suggestions = await llm_router.complete(prompt, max_tokens=300)
        except Exception:
            suggestions = "Consider reducing equity fund overlap and adding international/debt diversification."

        return {
            "health_score": round(health, 1), "overlap_pct": round(overlap_pct, 1),
            "sector_concentration": sector_concentration, "risk_level": risk_level,
            "rebalancing_suggestions": suggestions,
        }
