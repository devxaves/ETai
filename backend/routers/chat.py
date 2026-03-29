"""
routers/chat.py — Portfolio upload, RAG chat, and session management endpoints.
"""

import asyncio
import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import ChatSession

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    session_id: str
    message: str
    history: List[dict] = []


@router.post("/portfolio/upload")
async def upload_portfolio(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/portfolio/upload — Upload CAMS/KFintech PDF or CSV statement.
    Returns session_id + full portfolio analysis.
    """
    from backend.agents.market_chatgpt import PortfolioChatAgent

    if not session_id:
        session_id = str(uuid.uuid4())

    agent = PortfolioChatAgent()

    # Read file bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    # Parse the portfolio statement
    portfolio = await agent.parse_cams_statement(file_bytes, filename=file.filename or "")

    # Embed portfolio context in ChromaDB
    try:
        await agent.embed_and_store_portfolio(session_id, portfolio)
    except Exception as e:
        logger.warning("Embedding failed, continuing without RAG", error=str(e))

    # Analyze portfolio health
    analysis = await agent.analyze_portfolio_health(portfolio)

    # Store session in DB
    portfolio_dict = portfolio.to_dict()
    session = ChatSession(
        session_id=session_id,
        portfolio_data=portfolio_dict,
        messages=[],
        portfolio_summary=portfolio.to_summary_text(),
    )
    # Upsert (update if exists)
    existing = await db.get(ChatSession, session_id)
    if existing:
        existing.portfolio_data = portfolio_dict
        existing.portfolio_summary = portfolio.to_summary_text()
    else:
        db.add(session)
    await db.commit()

    return {
        "session_id": session_id,
        "portfolio": portfolio_dict,
        "analysis": analysis,
        "message": f"Portfolio loaded: {len(portfolio.holdings)} holdings. Total value: ₹{portfolio.total_value:,.0f}",
    }


@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    POST /api/chat — Send a message, get a portfolio-aware streaming response.
    """
    from backend.agents.market_chatgpt import PortfolioChatAgent, Portfolio

    # Load session
    session = await db.get(ChatSession, request.session_id)
    portfolio = None
    if session and session.portfolio_data:
        from backend.agents.market_chatgpt import Holding
        holdings_data = session.portfolio_data.get("holdings", [])
        holdings = [
            Holding(
                fund_name=h.get("fund_name", ""),
                units=float(h.get("units", 0)),
                current_value=float(h.get("current_value", 0)),
                invested_amount=float(h.get("invested_amount", 0)),
                xirr=float(h.get("xirr", 0)),
                category=h.get("category", ""),
            )
            for h in holdings_data
        ]
        portfolio = Portfolio(holdings=holdings, investor_name=session.portfolio_data.get("investor_name", ""))

    agent = PortfolioChatAgent()

    async def generate():
        full_response = ""
        try:
            async for chunk in agent.stream_chat(
                session_id=request.session_id,
                user_message=request.message,
                conversation_history=request.history,
                portfolio=portfolio,
            ):
                full_response += chunk
                yield f"data: {chunk}\n\n"
        except Exception as e:
            error_msg = "I encountered an issue. Please try again."
            yield f"data: {error_msg}\n\n"
            full_response = error_msg
        finally:
            yield "data: [DONE]\n\n"

        # Update session history in DB
        try:
            if session:
                messages = session.messages or []
                messages.append({"role": "user", "content": request.message})
                messages.append({"role": "assistant", "content": full_response})
                session.messages = messages
                await db.commit()
        except Exception as e:
            logger.warning("Session history update failed", error=str(e))

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/simple")
async def chat_simple(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    POST /api/chat/simple — Non-streaming chat for simpler clients.
    """
    from backend.agents.market_chatgpt import PortfolioChatAgent, Portfolio, Holding

    session = await db.get(ChatSession, request.session_id)
    portfolio = None
    if session and session.portfolio_data:
        holdings_data = session.portfolio_data.get("holdings", [])
        portfolio = Portfolio(
            holdings=[Holding(
                fund_name=h.get("fund_name", ""), units=float(h.get("units", 0)),
                current_value=float(h.get("current_value", 0)), invested_amount=float(h.get("invested_amount", 0)),
                xirr=float(h.get("xirr", 0)), category=h.get("category", ""),
            ) for h in holdings_data],
            investor_name=session.portfolio_data.get("investor_name", "")
        )

    agent = PortfolioChatAgent()
    response = await agent.chat(request.session_id, request.message, request.history, portfolio)

    if session:
        messages = list(session.messages or [])
        messages.extend([
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": response},
        ])
        session.messages = messages
        await db.commit()

    return {"response": response, "session_id": request.session_id}


@router.get("/chat/session/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """GET /api/chat/session/{session_id} — Get session history and portfolio summary."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "portfolio": session.portfolio_data,
        "portfolio_summary": session.portfolio_summary,
        "messages": session.messages or [],
        "created_at": session.created_at.isoformat(),
    }


@router.delete("/chat/session/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """DELETE /api/chat/session/{session_id} — Cleanup session and embeddings."""
    from backend.data.embeddings import delete_portfolio_context

    async def _delete_session_record() -> bool:
        session = await db.get(ChatSession, session_id)
        if not session:
            return False
        await db.delete(session)
        await db.commit()
        return True

    deleted = False
    try:
        deleted = await asyncio.wait_for(_delete_session_record(), timeout=3.0)
    except asyncio.TimeoutError:
        logger.warning("Session deletion timed out", session_id=session_id)
    except Exception as e:
        logger.warning("Session deletion failed", session_id=session_id, error=str(e))

    async def _cleanup_embeddings():
        try:
            await asyncio.wait_for(delete_portfolio_context(session_id), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning("Embedding cleanup timed out", session_id=session_id)
        except Exception as e:
            logger.warning("Embedding cleanup failed", error=str(e))

    asyncio.create_task(_cleanup_embeddings())

    if deleted:
        return {"message": f"Session {session_id} deleted successfully"}
    return {"message": f"Session {session_id} cleanup scheduled"}
