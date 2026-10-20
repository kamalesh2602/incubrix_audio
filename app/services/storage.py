import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService(ABC):
    """Abstract interface for storing generated job artifacts (audio stems, mix, manifest).

    Supports seamless swapping between local filesystem storage and S3-compatible
    cloud object storage (such as AWS S3, MinIO, or LocalStack).
    """

    @abstractmethod
    async def save_file(self, job_id: str, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Saves file bytes and returns the public or relative URL for retrieval."""
        pass

    @abstractmethod
    async def get_file_path(self, job_id: str, filename: str) -> Optional[Path]:
        """Returns the local Path if available, or downloads from remote storage to local cache."""
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


class S3StorageService(StorageService):
    """S3-compatible object storage service (AWS S3, MinIO, Ceph, LocalStack)."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ):
        import boto3
        from botocore.config import Config

        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.region = region or settings.S3_REGION

        key_id = access_key_id or (settings.S3_ACCESS_KEY_ID.get_secret_value() if settings.S3_ACCESS_KEY_ID else None)
        secret_key = secret_access_key or (settings.S3_SECRET_ACCESS_KEY.get_secret_value() if settings.S3_SECRET_ACCESS_KEY else None)

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

        self.cache_dir = Path(cache_dir or settings.STORAGE_DIR / "s3_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Idempotently creates bucket if running against local MinIO/mock storage."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created S3 bucket '{self.bucket_name}' at {self.endpoint_url or 'AWS'}")
            except Exception as exc:
                logger.warning(f"Could not automatically create bucket '{self.bucket_name}': {exc}")

    def _safe_filename(self, filename: str) -> str:
        return os.path.basename(filename).strip()

    def _s3_key(self, job_id: str, filename: str) -> str:
        safe_job_id = os.path.basename(job_id).strip()
        clean_name = self._safe_filename(filename)
        return f"{safe_job_id}/{clean_name}"

    async def save_file(self, job_id: str, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        clean_name = self._safe_filename(filename)
        key = self._s3_key(job_id, clean_name)

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        # Cache locally
        cached_job_dir = self.cache_dir / os.path.basename(job_id).strip()
        cached_job_dir.mkdir(parents=True, exist_ok=True)
        (cached_job_dir / clean_name).write_bytes(data)

        return self.get_file_url(job_id, clean_name)

    async def get_file_path(self, job_id: str, filename: str) -> Optional[Path]:
        clean_name = self._safe_filename(filename)
        cached_job_dir = self.cache_dir / os.path.basename(job_id).strip()
        cached_path = cached_job_dir / clean_name

        if cached_path.exists() and cached_path.is_file():
            return cached_path

        # Download from S3 to cache
        key = self._s3_key(job_id, clean_name)
        try:
            cached_job_dir.mkdir(parents=True, exist_ok=True)
            self.s3_client.download_file(self.bucket_name, key, str(cached_path))
            return cached_path
        except Exception as exc:
            logger.debug(f"Failed to retrieve S3 key '{key}': {exc}")
            return None

    def get_file_url(self, job_id: str, filename: str) -> str:
        clean_name = self._safe_filename(filename)
        key = self._s3_key(job_id, clean_name)
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{key}"
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"


def get_storage_service() -> StorageService:
    """Factory selecting the active StorageService based on configuration."""
    backend = getattr(settings, "STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3StorageService()
    return LocalStorageService()


# Default singleton instance
storage_service: StorageService = get_storage_service()
