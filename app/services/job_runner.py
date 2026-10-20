import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.models.job import Job, JobStatus
from app.models.schemas import JobResultSchema
from app.services.job_store import job_store
from app.services.provider import get_music_provider
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


async def run_job(job_id: str) -> None:
    """Executes a music generation job in the background, updating progress

    and persisting artifacts to storage.
    """
    job: Optional[Job] = await job_store.get_job(job_id)
    if not job:
        logger.error(f"Cannot run job {job_id}: job not found in store")
        return

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    job.progress = 0.05
    await job_store.update_job(job)

    provider = get_music_provider()

    async def progress_callback(progress_val: float) -> None:
        curr_job = await job_store.get_job(job_id)
        if curr_job and curr_job.status == JobStatus.RUNNING:
            curr_job.progress = min(0.95, max(curr_job.progress, round(progress_val, 2)))
            await job_store.update_job(curr_job)

    try:
        # Generate music stems, mix, and manifest
        artifacts = await provider.generate_music(
            job_id=job.job_id,
            request=job.request,
            progress_callback=progress_callback,
        )

        # Save audio mix
        mix_url = await storage_service.save_file(
            job_id=job.job_id,
            filename=artifacts.mix_filename,
            data=artifacts.mix_bytes,
            content_type="audio/wav",
        )

        # Save individual stems
        stem_urls = {}
        for stem_name, stem_bytes in artifacts.stem_bytes.items():
            filename = artifacts.stem_filenames[stem_name]
            url = await storage_service.save_file(
                job_id=job.job_id,
                filename=filename,
                data=stem_bytes,
                content_type="audio/wav",
            )
            stem_urls[stem_name] = url

        # Save music_manifest.json
        manifest_url = await storage_service.save_file(
            job_id=job.job_id,
            filename=artifacts.manifest_filename,
            data=artifacts.manifest_bytes,
            content_type="application/json",
        )

        # Update job with succeeded status and result metadata
        job = await job_store.get_job(job_id)
        if job:
            job.result = JobResultSchema(
                audio_url=mix_url,
                stems=stem_urls,
                manifest_url=manifest_url,
                duration_s=artifacts.duration_s,
                sample_rate=artifacts.sample_rate,
                channels=1,
                format="wav",
                stem_gains=artifacts.stem_gains,
            )
            job.status = JobStatus.SUCCEEDED
            job.progress = 1.0
            job.completed_at = datetime.now(timezone.utc)
            await job_store.update_job(job)
            logger.info(f"Job {job_id} succeeded")

    except Exception as exc:
        logger.exception(f"Job {job_id} failed with error: {exc}")
        job = await job_store.get_job(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await job_store.update_job(job)


def schedule_job(job_id: str) -> None:
    """Schedules background execution for the given job."""
    asyncio.create_task(run_job(job_id))
