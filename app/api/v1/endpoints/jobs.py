import io
import os
import zipfile
from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from app.core.errors import ConflictError, JobFailedError, NotFoundError
from app.models.job import JobStatus
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


@router.get(
    "/jobs/{job_id}/download",
    summary="Download complete job archive as ZIP",
    description="Downloads a ZIP archive containing mix.wav, mix.mp3 (if present), all separated stems under stems/, and music_manifest.json.",
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "ZIP archive containing generated mix, stems, and manifest",
        },
        404: {"description": "Job or artifact not found"},
        409: {"description": "Job is still in progress (queued/running) or failed"},
    },
)
async def download_job_archive(job_id: str):
    # 1. Fetch job from store
    job = await job_store.get_job(job_id)
    if not job:
        raise NotFoundError(f"Job with ID '{job_id}' was not found.")

    # 2. Check if job is still in progress
    if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise ConflictError(
            f"Job '{job_id}' is still in progress (status: {job.status.value}). ZIP archive is only available once the job has succeeded.",
            code="JOB_NOT_READY",
        )

    # 3. Check if job failed
    if job.status == JobStatus.FAILED:
        raise JobFailedError(
            f"Job '{job_id}' failed: {job.error or 'Processing failed.'}",
            code="JOB_FAILED",
        )

    if job.status != JobStatus.SUCCEEDED:
        raise ConflictError(
            f"Job '{job_id}' is not ready for download (status: {job.status.value}).",
            code="JOB_NOT_READY",
        )

    # 4. Locate required artifacts
    mix_path = await storage_service.get_file_path(job_id, "mix.wav")
    if not mix_path or not mix_path.exists():
        raise NotFoundError(f"Mix audio artifact 'mix.wav' for job '{job_id}' was not found.")

    manifest_path = await storage_service.get_file_path(job_id, "music_manifest.json")
    if not manifest_path or not manifest_path.exists():
        raise NotFoundError(f"Manifest artifact 'music_manifest.json' for job '{job_id}' was not found.")

    mp3_path = await storage_service.get_file_path(job_id, "mix.mp3")

    # Locate stems
    stem_paths = []
    if job.result and job.result.stems:
        for stem_name, stem_url in job.result.stems.items():
            stem_filename = stem_url.split("/")[-1]
            stem_p = await storage_service.get_file_path(job_id, stem_filename)
            if stem_p and stem_p.exists():
                stem_paths.append(stem_p)

    # Fallback to inspecting storage directory if result.stems was empty
    if not stem_paths and hasattr(storage_service, "base_dir"):
        safe_job_id = os.path.basename(job_id).strip()
        job_dir = storage_service.base_dir / safe_job_id
        if job_dir.exists():
            for p in job_dir.glob("*.wav"):
                if p.name != "mix.wav":
                    stem_paths.append(p)

    if not stem_paths:
        raise NotFoundError(f"Instrument stem artifacts for job '{job_id}' were not found.")

    # 5. Build ZIP archive in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add mix.wav
        zf.write(mix_path, arcname="mix.wav")

        # Add mix.mp3 if exists
        if mp3_path and mp3_path.exists():
            zf.write(mp3_path, arcname="mix.mp3")

        # Add manifest
        zf.write(manifest_path, arcname="music_manifest.json")

        # Add stems under stems/
        seen_arcnames = set()
        for stem_p in stem_paths:
            arcname = f"stems/{stem_p.name}"
            if arcname not in seen_arcnames:
                zf.write(stem_p, arcname=arcname)
                seen_arcnames.add(arcname)

    zip_bytes = buf.getvalue()
    filename = f"incubrix_audio_{job_id}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )
