import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.core.config import settings


class StorageService(ABC):
    """Abstract interface for storing generated job artifacts (audio stems, mix, manifest).

    Allows seamless swapping between local filesystem storage and cloud object storage
    such as AWS S3 or MinIO in future production deployments.
    """

    @abstractmethod
    async def save_file(self, job_id: str, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Saves file bytes and returns the public or relative URL for retrieval."""
        pass

    @abstractmethod
    async def get_file_path(self, job_id: str, filename: str) -> Optional[Path]:
        """Returns the local Path if available, or None."""
        pass

    @abstractmethod
    def get_file_url(self, job_id: str, filename: str) -> str:
        """Returns the retrieval URL for the artifact."""
        pass


class LocalStorageService(StorageService):
    """Local filesystem storage service.

    Stores files locally under STORAGE_DIR / job_id / filename.
    Provides URLs routed through the FastAPI artifact endpoint.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or settings.STORAGE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_filename(self, filename: str) -> str:
        # Sanitize filename to prevent directory traversal
        return os.path.basename(filename).strip()

    def _job_dir(self, job_id: str) -> Path:
        safe_job_id = os.path.basename(job_id).strip()
        job_path = self.base_dir / safe_job_id
        job_path.mkdir(parents=True, exist_ok=True)
        return job_path

    async def save_file(self, job_id: str, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        clean_name = self._safe_filename(filename)
        dest_dir = self._job_dir(job_id)
        file_path = dest_dir / clean_name
        file_path.write_bytes(data)
        return self.get_file_url(job_id, clean_name)

    async def get_file_path(self, job_id: str, filename: str) -> Optional[Path]:
        clean_name = self._safe_filename(filename)
        dest_dir = self._job_dir(job_id)
        file_path = dest_dir / clean_name
        if file_path.exists() and file_path.is_file():
            return file_path
        return None

    def get_file_url(self, job_id: str, filename: str) -> str:
        clean_name = self._safe_filename(filename)
        return f"{settings.API_V1_PREFIX}/jobs/{job_id}/artifacts/{clean_name}"


# Default singleton instance
storage_service: StorageService = LocalStorageService()
