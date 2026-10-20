import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Optional

from app.models.job import Job


class JobStore(ABC):
    """Abstract interface for managing job persistence and idempotency tracking.

    Designed to be cleanly replaced with persistent storage backends
    such as PostgreSQL or Redis in production environments.
    """

    @abstractmethod
    async def create_job(self, job: Job) -> Job:
        """Stores a new job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieves a job by its unique identifier."""
        pass

    @abstractmethod
    async def update_job(self, job: Job) -> Job:
        """Updates an existing job's state."""
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Optional[Job]:
        """Retrieves a job associated with an idempotency key if present."""
        pass

    @abstractmethod
    async def set_idempotency_key(self, key: str, job_id: str) -> None:
        """Maps an idempotency key to a job ID."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clears all jobs and idempotency keys (primarily used in testing)."""
        pass


class InMemoryJobStore(JobStore):
    """In-memory implementation of JobStore using an asyncio lock for concurrency safety.

    CRITICAL NOTICE / LIMITATION:
    This storage implementation is strictly for local development and milestone testing.
    In-memory jobs DO NOT survive application restarts or process termination, and
    state is not shared across multi-worker deployments.
    THIS IS NOT PRODUCTION-READY. Replace with Redis or PostgreSQL for production.
    """

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job: Job) -> Job:
        async with self._lock:
            self._jobs[job.job_id] = job.model_copy(deep=True)
            if job.idempotency_key:
                self._idempotency_map[job.idempotency_key] = job.job_id
            return job.model_copy(deep=True)

    async def get_job(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return job.model_copy(deep=True)
            return None

    async def update_job(self, job: Job) -> Job:
        async with self._lock:
            self._jobs[job.job_id] = job.model_copy(deep=True)
            return job.model_copy(deep=True)

    async def get_by_idempotency_key(self, key: str) -> Optional[Job]:
        async with self._lock:
            job_id = self._idempotency_map.get(key)
            if job_id and job_id in self._jobs:
                return self._jobs[job_id].model_copy(deep=True)
            return None

    async def set_idempotency_key(self, key: str, job_id: str) -> None:
        async with self._lock:
            self._idempotency_map[key] = job_id

    async def clear(self) -> None:
        async with self._lock:
            self._jobs.clear()
            self._idempotency_map.clear()


# Default singleton instance
job_store: JobStore = InMemoryJobStore()
