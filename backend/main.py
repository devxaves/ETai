"""
main.py — FastAPI application entry point.
Registers all routers, configures CORS, initializes DB on startup.
"""

import os
import structlog
from contextlib import asynccontextmanager
import sys
import os

# Ensure /app is in sys.path for absolute imports inside docker
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.routers import signals, patterns, chat, market, video

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    # Startup
    logger.info("ET Investor Intelligence starting up...")
    os.makedirs("data", exist_ok=True)
    os.makedirs("/tmp/videos", exist_ok=True)
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("ET Investor Intelligence shutting down")


app = FastAPI(
    title="ET Investor Intelligence API",
    description=(
        "AI-powered investment intelligence for the Indian retail investor. "
        "4 agents: Opportunity Radar | Chart Patterns | Portfolio Chat | Video Engine."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*", 
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(signals.router)
app.include_router(patterns.router)
app.include_router(chat.router)
app.include_router(market.router)
app.include_router(video.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check():
    """Liveness probe for Docker/k8s."""
    return {
        "status": "healthy",
        "service": "ET Investor Intelligence",
        "version": "1.0.0",
    }


@app.get("/", tags=["health"])
async def root():
    """Root endpoint with API overview."""
    return {
        "name": "ET Investor Intelligence API",
        "version": "1.0.0",
        "description": "India's Bloomberg Terminal for the retail investor",
        "endpoints": {
            "signals": "/api/signals",
            "patterns": "/api/patterns/{symbol}",
            "chat": "/api/chat",
            "portfolio_upload": "/api/portfolio/upload",
            "market": "/api/market/summary",
            "video": "/api/video/generate",
            "docs": "/docs",
            "websocket": "ws://localhost:8000/api/signals/live",
        },
        "agents": [
            "1. Opportunity Radar — SEBI bulk deal + insider pattern scanner",
            "2. Chart Pattern Intelligence — TA-Lib + backtest engine",
            "3. Portfolio-Aware Chat — CAMS RAG chatbot",
            "4. AI Video Engine — auto market wrap video generator",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", 8000)),
        reload=os.getenv("APP_ENV", "development") == "development",
        workers=1,
    )
