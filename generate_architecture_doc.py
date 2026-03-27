"""
generate_architecture_doc.py — Generates the 2-page architecture PDF.
Run: python generate_architecture_doc.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderPDF
import os


def create_architecture_pdf(output_path="ET_Architecture.pdf"):
    """Generate a 2-page architecture document."""

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=22, textColor=HexColor("#0a0a0a"), spaceAfter=10)
    heading_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=HexColor("#1a1a1a"), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14)
    center_style = ParagraphStyle("Center", parent=styles["BodyText"], alignment=TA_CENTER, fontSize=10)
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=HexColor("#666666"))

    elements = []

    # ── PAGE 1: System Architecture ──────────────────────────────────────
    elements.append(Paragraph("ET Investor Intelligence", title_style))
    elements.append(Paragraph("System Architecture Document — ET AI Hackathon 2026", center_style))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("1. Agent Architecture", heading_style))
    elements.append(Paragraph(
        "The system consists of 4 AI agents, each specializing in a different aspect of market intelligence. "
        "All agents share a common LLM Router (Claude → Gemini → Groq fallback) and persistent data layer.",
        body_style
    ))
    elements.append(Spacer(1, 8))

    agent_data = [
        ["Agent", "Function", "Key Tech", "Output"],
        ["Opportunity Radar", "SEBI bulk deal analysis\n+ insider patterns", "FinBERT + LLM", "Confidence-scored signals"],
        ["Chart Patterns", "Candlestick detection\n+ backtest", "TA-Lib + pandas-ta", "Patterns + success rates"],
        ["Portfolio Chat", "CAMS parsing +\nportfolio-aware RAG", "ChromaDB + LLM", "Personalized advice"],
        ["Video Engine", "Auto market recap\nvideo generation", "gTTS + MoviePy", "60-sec MP4 videos"],
    ]
    t = Table(agent_data, colWidths=[2.5 * cm, 4.5 * cm, 3.5 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0a0a0a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#f5f5f5")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("2. Data Flow Pipeline", heading_style))
    elements.append(Paragraph(
        "<b>NSE Bhavcopy + SEBI Bulk Deals</b> → Data Fetchers (Python) → <b>SQLite DB</b> → "
        "AI Agents (Celery tasks, 6 PM IST daily) → <b>Signals + Patterns</b> → Redis Pub/Sub → "
        "<b>WebSocket</b> → Next.js Frontend (real-time updates)",
        body_style
    ))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("3. Technology Stack", heading_style))
    stack_data = [
        ["Layer", "Technology"],
        ["Backend", "FastAPI + uvicorn (async Python)"],
        ["Database", "SQLite (SQLAlchemy async) + ChromaDB (vectors)"],
        ["Task Queue", "Celery + Redis (pub/sub + broker)"],
        ["LLM (Primary)", "Anthropic Claude claude-sonnet-4-20250514"],
        ["LLM (Fallback 1)", "Google Gemini 1.5 Flash (free tier)"],
        ["LLM (Fallback 2)", "Groq Llama 3.1 8B Instant (free tier)"],
        ["Sentiment", "FinBERT (ProsusAI/finbert, local)"],
        ["Embeddings", "all-MiniLM-L6-v2 (local, zero cost)"],
        ["Pattern Detection", "TA-Lib + pandas-ta"],
        ["Video", "gTTS / ElevenLabs + MoviePy + matplotlib"],
        ["Frontend", "Next.js 14 + TailwindCSS + TradingView Charts"],
        ["Deployment", "Docker Compose (4 containers)"],
    ]
    t2 = Table(stack_data, colWidths=[3.5 * cm, 12 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0a0a0a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (0, -1), HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("4. LLM Fallback Chain", heading_style))
    elements.append(Paragraph(
        "Claude (best quality, paid) → <i>on failure</i> → Gemini Flash (free, 1500/day) → "
        "<i>on failure</i> → Groq Llama 3.1 (free, fastest). "
        "Exponential backoff retry on 429 rate limits. All calls through centralized LLMRouter class.",
        body_style
    ))

    # ── PAGE 2: Communication & Error Handling ───────────────────────────
    elements.append(PageBreak())

    elements.append(Paragraph("5. Agent Communication & Scheduling", heading_style))
    schedule_data = [
        ["Time (IST)", "Task", "Agent"],
        ["6:00 PM", "Download NSE Bhavcopy + SEBI deals", "Data Layer"],
        ["6:30 PM", "Scan bulk deals + insider patterns", "Opportunity Radar"],
        ["7:00 PM", "Candlestick pattern scan (Nifty 50)", "Chart Patterns"],
        ["7:30 PM", "Refresh ChromaDB embeddings", "Portfolio Chat"],
    ]
    t3 = Table(schedule_data, colWidths=[3 * cm, 8 * cm, 4.5 * cm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#26a69a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t3)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "Agents communicate via <b>Redis pub/sub</b>: when Opportunity Radar detects a new signal, "
        "it publishes to the 'signals_live' channel. The WebSocket endpoint in FastAPI subscribes "
        "and broadcasts to all connected frontend clients in real-time.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("6. Error Recovery Strategy", heading_style))
    error_data = [
        ["Failure Mode", "Recovery Strategy"],
        ["LLM rate limit (429)", "Exponential backoff (2s, 4s, 8s) → fallback to next provider"],
        ["NSE/SEBI data unavailable", "Retry 3x with backoff → use cached data → mock fallback"],
        ["TA-Lib import fails", "Auto-fallback to pandas-ta pure Python implementation"],
        ["ChromaDB write fails", "Continue without RAG context (graceful degradation)"],
        ["Redis disconnected", "WebSocket sends demo signals, Celery retries on reconnect"],
        ["PDF parsing fails", "LLM-based text extraction → sample portfolio fallback"],
        ["Video rendering fails", "Fallback to simple title-card-only video"],
    ]
    t4 = Table(error_data, colWidths=[5 * cm, 10.5 * cm])
    t4.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#ef5350")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t4)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("7. Audit Trail", heading_style))
    elements.append(Paragraph(
        "Every agent decision is logged to the SQLite database with: timestamp, agent name, "
        "input parameters, output (signal/pattern/response), confidence score, LLM provider used, "
        "and raw data JSON. This enables full reproducibility and post-hoc analysis of signal quality.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("8. Deployment Architecture", heading_style))
    deploy_data = [
        ["Container", "Image", "Purpose", "Port"],
        ["et-backend", "python:3.11-slim + TA-Lib", "FastAPI API server", "8000"],
        ["et-redis", "redis:7-alpine", "Pub/sub + Celery broker", "6379"],
        ["et-celery-worker", "Same as backend", "Background task execution", "—"],
        ["et-celery-beat", "Same as backend", "Cron scheduler (daily scans)", "—"],
    ]
    t5 = Table(deploy_data, colWidths=[3.5 * cm, 4.5 * cm, 5 * cm, 2.5 * cm])
    t5.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#3b82f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t5)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph(
        "<i>One command deployment: <b>docker-compose up --build</b></i>",
        center_style
    ))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        "ET Investor Intelligence — Built for ET AI Hackathon 2026 | PS6: AI for the Indian Investor",
        ParagraphStyle("Footer", parent=small_style, alignment=TA_CENTER)
    ))

    doc.build(elements)
    print(f"✅ Architecture document saved to {output_path}")


if __name__ == "__main__":
    create_architecture_pdf()
