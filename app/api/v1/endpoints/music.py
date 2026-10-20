from pathlib import Path
import uuid
from typing import Optional
from fastapi import APIRouter, File, Header, Response, UploadFile, status

from app.core.config import settings
from app.core.errors import ValidationAppError
from app.models.job import Job, JobStatus
from app.models.schemas import AudioUploadResponse, MusicJobRequest, MusicJobResponse
from app.services.job_runner import schedule_job
from app.services.job_store import job_store
from app.services.storage import storage_service

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


@router.post(
    "/audio/upload",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio file (narration or reference)",
    description="Uploads an audio file (.wav, .mp3, .flac, .ogg) for use in music generation requests.",
)
@router.post(
    "/music/upload",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def upload_audio_file(
    file: UploadFile = File(..., description="Audio file to upload (.wav, .mp3, .flac, .ogg)"),
) -> AudioUploadResponse:
    # 1. Validate file extension and MIME type
    allowed_exts = {".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_exts:
        raise ValidationAppError(
            f"Unsupported audio format '{ext}'. Allowed extensions: {sorted(list(allowed_exts))}"
        )

    # 2. Read content & validate size (max 50 MB)
    content = await file.read()
    if not content:
        raise ValidationAppError("Uploaded audio file is empty.")
    if len(content) > 50 * 1024 * 1024:
        raise ValidationAppError("Audio file exceeds maximum allowed size of 50 MB.")

    upload_id = str(uuid.uuid4())
    safe_name = f"{upload_id}_{file.filename}"
    content_type = file.content_type or "audio/wav"

    url = await storage_service.save_file("uploads", safe_name, content, content_type)

    return AudioUploadResponse(
        upload_id=upload_id,
        filename=file.filename or safe_name,
        content_type=content_type,
        size_bytes=len(content),
        url=url,
        message="Audio file uploaded successfully",
    )
