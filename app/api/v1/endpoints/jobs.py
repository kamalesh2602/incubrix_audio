from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.errors import NotFoundError
from app.models.schemas import JobStatusResponse
from app.services.job_store import job_store
from app.services.storage import storage_service

router = APIRouter()


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and results",
    description="Returns current status (queued, running, succeeded, failed), progress, and artifact links.",
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = await job_store.get_job(job_id)
    if not job:
        raise NotFoundError(f"Job with ID '{job_id}' was not found.")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        result=job.result,
    )


@router.get(
    "/jobs/{job_id}/artifacts/{filename}",
    summary="Download generated artifact",
    description="Downloads audio files (.wav) or manifest (.json) produced by a job.",
)
async def get_job_artifact(job_id: str, filename: str):
    file_path = await storage_service.get_file_path(job_id, filename)
    if not file_path or not file_path.exists():
        raise NotFoundError(f"Artifact '{filename}' for job '{job_id}' was not found.")

    # Determine media type based on extension
    suffix = file_path.suffix.lower()
    media_types = {
        ".wav": "audio/wav",
        ".json": "application/json",
        ".mp3": "audio/mpeg",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )
