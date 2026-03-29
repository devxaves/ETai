"""
routers/video.py — Video generation endpoints: generate, status, download, script.
"""

import os
import uuid
import asyncio
from datetime import date, datetime
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from backend.database import get_db
from backend.models import VideoJob

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/video", tags=["video"])

VIDEO_DIR = "/tmp/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

# Fast status cache to avoid SQLite lock contention during long video jobs.
_video_job_cache: dict[str, dict] = {}


class VideoGenerateRequest(BaseModel):
    """Request to generate a new market recap video."""
    type: str  # daily_wrap | sector_rotation | top_signals | fii_dii_flow
    period: str = "today"  # today | this_week | this_month


@router.post("/generate")
async def generate_video(
    request: VideoGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/video/generate — Start async video generation, returns job_id."""
    job_id = str(uuid.uuid4())

    job = VideoJob(
        job_id=job_id,
        video_type=request.type,
        period=request.period,
        status="pending",
        progress=0,
    )
    db.add(job)
    await db.commit()

    _video_job_cache[job_id] = {
        "status": "pending",
        "progress": 0,
        "error": None,
    }

    asyncio.create_task(_run_video_generation(job_id, request.type, request.period))

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Video generation started. Check /api/video/status/{job_id}",
    }


@router.get("/status/{job_id}")
async def get_video_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """GET /api/video/status/{job_id} — Check generation progress."""
    cached = _video_job_cache.get(job_id)
    if cached:
        return {
            "job_id": job_id,
            "status": cached.get("status", "pending"),
            "progress": cached.get("progress", 0),
            "video_url": f"/api/video/download/{job_id}" if cached.get("status") == "completed" else None,
            "error": cached.get("error"),
        }

    job = await db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    return {
        "job_id": job_id,
        "status": job.status,
        "progress": job.progress,
        "video_url": f"/api/video/download/{job_id}" if job.status == "completed" else None,
        "error": job.error_message,
    }


@router.get("/download/{job_id}")
async def download_video(job_id: str, db: AsyncSession = Depends(get_db)):
    """GET /api/video/download/{job_id} — Stream the MP4 file."""
    job = await db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Video not ready: {job.status}")
    if not job.video_path or not os.path.exists(job.video_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    return FileResponse(
        path=job.video_path,
        media_type="video/mp4",
        filename=f"et_market_wrap_{job_id[:8]}.mp4",
    )


@router.get("/script/{job_id}")
async def get_video_script(job_id: str, db: AsyncSession = Depends(get_db)):
    """GET /api/video/script/{job_id} — Get the generated narration script."""
    job = await db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    return {
        "job_id": job_id,
        "script": job.script_text,
        "video_type": job.video_type,
        "period": job.period,
        "status": job.status,
    }


async def _run_video_generation(job_id: str, video_type: str, period: str):
    """Background task: generate the video and update job status in DB."""
    from backend.agents.video_engine import VideoScriptAgent
    from backend.database import AsyncSessionLocal

    async def update_job(**fields):
        cache_entry = _video_job_cache.setdefault(job_id, {"status": "pending", "progress": 0, "error": None})
        cache_entry["status"] = fields.get("status", cache_entry.get("status"))
        cache_entry["progress"] = fields.get("progress", cache_entry.get("progress", 0))
        cache_entry["error"] = fields.get("error_message", cache_entry.get("error"))

        async with AsyncSessionLocal() as db:
            job = await db.get(VideoJob, job_id)
            if not job:
                return False
            for key, value in fields.items():
                setattr(job, key, value)
            await db.commit()
            return True

    try:
        exists = await update_job(status="processing", progress=10)
        if not exists:
            return

        agent = VideoScriptAgent()
        target_date = date.today()

        script = await agent.generate_market_wrap_script(target_date)
        await update_job(script_text=script.narration_text, progress=40)

        video_path = await agent.generate_video(script, job_id=job_id)
        await update_job(progress=90)

        await update_job(
            video_path=video_path,
            status="completed",
            progress=100,
            completed_at=datetime.utcnow(),
        )
        logger.info("Video job completed", job_id=job_id, path=video_path)

    except Exception as e:
        logger.error("Video job failed", job_id=job_id, error=str(e))
        await update_job(status="failed", error_message=str(e))
