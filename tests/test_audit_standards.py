import io
import json
import uuid
import wave
import pytest
import yaml
from pathlib import Path
from httpx import AsyncClient

from app.core.config import settings
from app.core.logging import JSONLogFormatter
from app.services.storage import S3StorageService


def test_openapi_specification_is_3_1_and_matches_api():
    openapi_path = Path("openapi.yaml")
    assert openapi_path.exists(), "openapi.yaml file is missing from repository root"

    with open(openapi_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # 1. Verify OpenAPI 3.1.0 version
    assert spec.get("openapi") == "3.1.0", f"Expected OpenAPI 3.1.0, found: {spec.get('openapi')}"

    # 2. Verify all core paths are documented
    paths = spec.get("paths", {})
    required_routes = [
        "/health",
        "/ready",
        "/api/v1/music/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/download",
        "/api/v1/jobs/{job_id}/artifacts/{filename}",
        "/api/v1/audio/upload",
    ]
    for route in required_routes:
        assert route in paths, f"Route '{route}' is not documented in openapi.yaml"


@pytest.mark.asyncio
async def test_correlation_id_middleware(async_client: AsyncClient):
    # 1. Custom correlation ID passed in header
    custom_id = "test-corr-abc-123"
    res1 = await async_client.get("/health", headers={"X-Correlation-ID": custom_id})
    assert res1.status_code == 200
    assert res1.headers.get("X-Correlation-ID") == custom_id

    # 2. No correlation ID provided -> engine automatically generates UUID
    res2 = await async_client.get("/health")
    assert res2.status_code == 200
    generated_id = res2.headers.get("X-Correlation-ID")
    assert generated_id is not None
    assert len(generated_id) > 10
    uuid.UUID(generated_id)  # Validate it is a valid UUID


def test_structured_json_log_formatter():
    import logging

    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_file.py",
        lineno=42,
        msg="Test structured log message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    log_data = json.loads(formatted)

    assert log_data["level"] == "INFO"
    assert log_data["logger"] == "test_logger"
    assert log_data["message"] == "Test structured log message"
    assert "timestamp" in log_data
    assert "location" in log_data


@pytest.mark.asyncio
async def test_audio_file_upload_success_and_validation(async_client: AsyncClient):
    # 1. Create a dummy WAV file in memory
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * 44100)  # 1 second of silence
    wav_bytes = buf.getvalue()

    # 2. Upload valid audio
    files = {"file": ("narration.wav", wav_bytes, "audio/wav")}
    upload_res = await async_client.post("/api/v1/audio/upload", files=files)
    assert upload_res.status_code == 201
    upload_data = upload_res.json()

    assert "upload_id" in upload_data
    assert upload_data["filename"] == "narration.wav"
    assert upload_data["content_type"] == "audio/wav"
    assert upload_data["size_bytes"] == len(wav_bytes)
    assert "url" in upload_data

    # 3. Upload invalid file extension -> 422 structured error
    invalid_files = {"file": ("malicious.exe", b"MZexecutable", "application/octet-stream")}
    err_res = await async_client.post("/api/v1/audio/upload", files=invalid_files)
    assert err_res.status_code == 422
    err_data = err_res.json()
    assert err_data["error"]["code"] == "VALIDATION_ERROR"
    assert "unsupported" in err_data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_s3_storage_service_interface(tmp_path: Path, monkeypatch):
    from unittest.mock import MagicMock

    # Verify S3StorageService saves and retrieves keys
    mock_s3 = MagicMock()
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: mock_s3)

    cache_dir = tmp_path / "s3_cache"
    s3_svc = S3StorageService(
        endpoint_url="http://localhost:9000",
        bucket_name="test-bucket",
        access_key_id="test-key",
        secret_access_key="test-secret",
        cache_dir=cache_dir,
    )

    # Test save_file
    url = await s3_svc.save_file("job-123", "mix.wav", b"AUDIOBYTES", "audio/wav")
    assert "job-123/mix.wav" in url
    assert mock_s3.put_object.called

    # Test get_file_path from local cache
    cached_path = await s3_svc.get_file_path("job-123", "mix.wav")
    assert cached_path is not None
    assert cached_path.exists()
    assert cached_path.read_bytes() == b"AUDIOBYTES"
