"""
models.py — SQLAlchemy ORM models for all persistent data.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Date, JSON, Text, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


def generate_uuid() -> str:
    """Generate a unique ID string."""
    return str(uuid.uuid4())


class StockDaily(Base):
    """Daily OHLCV data for a stock symbol (from NSE Bhavcopy + yfinance)."""
    __tablename__ = "stocks_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=True)
    high: Mapped[float] = mapped_column(Float, nullable=True)
    low: Mapped[float] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BulkDeal(Base):
    """SEBI bulk and block deal records."""
    __tablename__ = "bulk_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=True)
    deal_type: Mapped[str] = mapped_column(String(10), nullable=True)  # BUY / SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=True)
    deal_category: Mapped[str] = mapped_column(String(10), default="BULK")  # BULK / BLOCK
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Signal(Base):
    """AI-generated trading signals from all agents."""
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "BULK_DEAL", "INSIDER_PATTERN", "CHART_PATTERN", "COMPOSITE"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0–100
    explanation: Mapped[str] = mapped_column(Text, nullable=True)  # LLM explanation
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    is_bullish: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ChatSession(Base):
    """Portfolio chat sessions with conversation history."""
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    portfolio_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    portfolio_summary: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PatternHistory(Base):
    """Historical chart pattern detections with backtest results."""
    __tablename__ = "pattern_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    success_rate: Mapped[float] = mapped_column(Float, nullable=True)  # 0–100%
    price_at_detection: Mapped[float] = mapped_column(Float, nullable=True)
    price_after_10d: Mapped[float] = mapped_column(Float, nullable=True)
    rsi: Mapped[float] = mapped_column(Float, nullable=True)
    macd: Mapped[float] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=True)


class VideoJob(Base):
    """Video generation job tracking."""
    __tablename__ = "video_jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    video_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | processing | completed | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0–100
    script_text: Mapped[str] = mapped_column(Text, nullable=True)
    video_path: Mapped[str] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
