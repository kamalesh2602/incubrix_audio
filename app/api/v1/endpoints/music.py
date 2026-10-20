import uuid
from typing import Optional
from fastapi import APIRouter, Header, Response, status

from app.core.config import settings
from app.models.job import Job, JobStatus
from app.models.schemas import MusicJobRequest, MusicJobResponse
from app.services.job_runner import schedule_job
from app.services.job_store import job_store

router = APIRouter()


@router.post(
    "/music/jobs",
    response_model=MusicJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create background music generation job",
    description="Accepts music generation parameters and queues a background synthesis job.",
)
async def create_music_job(
    request: MusicJobRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> MusicJobResponse:
    # 1. Check for idempotent replay
    if idempotency_key:
        clean_key = idempotency_key.strip()
        if clean_key:
            existing_job = await job_store.get_by_idempotency_key(clean_key)
            if existing_job:
                response.headers["Idempotent-Replay"] = "true"
                # If existing job is still queued, return 202; otherwise return 200
                if existing_job.status != JobStatus.QUEUED:
                    response.status_code = status.HTTP_200_OK
                else:
                    response.status_code = status.HTTP_202_ACCEPTED

                return MusicJobResponse(
                    job_id=existing_job.job_id,
                    status=existing_job.status.value,
                    created_at=existing_job.created_at,
                    message="Idempotent request: returning existing job without duplicating work",
                    job_url=f"{settings.API_V1_PREFIX}/jobs/{existing_job.job_id}",
                )

    # 2. Create new job
    job_id = str(uuid.uuid4())
    stored_idemp_key = idempotency_key.strip() if idempotency_key else None

    job = Job(
        job_id=job_id,
        request=request,
        status=JobStatus.QUEUED,
        progress=0.0,
        idempotency_key=stored_idemp_key,
    )

    await job_store.create_job(job)

    # 3. Schedule asynchronous in-process generation
    schedule_job(job_id)

    response.status_code = status.HTTP_202_ACCEPTED
    return MusicJobResponse(
        job_id=job_id,
        status="queued",
        created_at=job.created_at,
        message="Job accepted and queued for processing",
        job_url=f"{settings.API_V1_PREFIX}/jobs/{job_id}",
    )
