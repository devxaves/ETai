"""
routers/video.py — Video generation endpoints: generate, status, download, script.
"""

import os
import uuid
from datetime import date, datetime
import structlog
from fastapi import APIRouter, HTTPException, BackgroundTasks
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


class VideoGenerateRequest(BaseModel):
    """Request to generate a new market recap video."""
    type: str  # daily_wrap | sector_rotation | top_signals | fii_dii_flow
    period: str = "today"  # today | this_week | this_month


@router.post("/generate")
async def generate_video(
    request: VideoGenerateRequest,
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(_run_video_generation, job_id, request.type, request.period)

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Video generation started. Check /api/video/status/{job_id}",
    }


@router.get("/status/{job_id}")
async def get_video_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """GET /api/video/status/{job_id} — Check generation progress."""
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

    async with AsyncSessionLocal() as db:
        job = await db.get(VideoJob, job_id)
        if not job:
            return

        try:
            job.status = "processing"
            job.progress = 10
            await db.commit()

            agent = VideoScriptAgent()

            # Determine target date
            target_date = date.today()

            # Generate script
            script = await agent.generate_market_wrap_script(target_date)
            job.script_text = script.narration_text
            job.progress = 40
            await db.commit()

            # Generate video
            video_path = await agent.generate_video(script, job_id=job_id)
            job.progress = 90
            await db.commit()

            job.video_path = video_path
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            await db.commit()

            logger.info("Video job completed", job_id=job_id, path=video_path)

        except Exception as e:
            logger.error("Video job failed", job_id=job_id, error=str(e))
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
