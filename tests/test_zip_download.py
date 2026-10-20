import asyncio
import io
import json
import uuid
import wave
import zipfile
import pytest
from httpx import AsyncClient

from app.models.job import Job, JobStatus
from app.models.schemas import JobResultSchema, MusicJobRequest
from app.services.job_store import job_store
from app.services.storage import storage_service


@pytest.mark.asyncio
async def test_zip_download_success_and_archive_contents(async_client: AsyncClient):
    payload = {
        "prompt": "Uplifting acoustic guitar and light drums for travel vlog",
        "duration_s": 5.0,
        "tempo_bpm": 120,
        "key": "G major",
        "output": {
            "sample_rate": 44100,
            "target_lufs": -14.0,
            "formats": ["wav"],
        },
    }

    # 1. Submit music generation job
    post_res = await async_client.post("/api/v1/music/jobs", json=payload)
    assert post_res.status_code == 202
    job_id = post_res.json()["job_id"]

    # 2. Poll until completed
    completed = False
    for _ in range(40):
        status_res = await async_client.get(f"/api/v1/jobs/{job_id}")
        assert status_res.status_code == 200
        if status_res.json().get("status") == "succeeded":
            completed = True
            break
        await asyncio.sleep(0.1)

    assert completed, "Job did not complete in time"

    # 3. Call GET /api/v1/jobs/{job_id}/download
    download_res = await async_client.get(f"/api/v1/jobs/{job_id}/download")
    assert download_res.status_code == 200
    assert download_res.headers.get("content-type") == "application/zip"
    
    disposition = download_res.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert f'filename="incubrix_audio_{job_id}.zip"' in disposition

    # 4. Inspect ZIP archive contents
    zip_bytes = download_res.content
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()

        # Check mix.wav exists and is valid WAV
        assert "mix.wav" in namelist
        mix_data = zf.read("mix.wav")
        assert len(mix_data) > 0
        with wave.open(io.BytesIO(mix_data), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 44100
            assert wf.getsampwidth() == 2

        # Check music_manifest.json exists and is valid
        assert "music_manifest.json" in namelist
        manifest_raw = zf.read("music_manifest.json")
        manifest_data = json.loads(manifest_raw.decode("utf-8"))
        assert manifest_data["job_id"] == job_id
        assert manifest_data["request"]["prompt"] == payload["prompt"]

        # Check all instrument stems are located under stems/
        stem_entries = [name for name in namelist if name.startswith("stems/") and not name.endswith("/")]
        assert len(stem_entries) >= 3, f"Expected at least 3 stems, found: {stem_entries}"

        for stem_name in stem_entries:
            stem_data = zf.read(stem_name)
            assert len(stem_data) > 0
            with wave.open(io.BytesIO(stem_data), "rb") as stem_wf:
                assert stem_wf.getframerate() == 44100
                assert stem_wf.getsampwidth() == 2


@pytest.mark.asyncio
async def test_zip_download_includes_mp3_when_present(async_client: AsyncClient):
    payload = {
        "prompt": "Ambient study music",
        "duration_s": 5.0,
    }

    # Submit job
    post_res = await async_client.post("/api/v1/music/jobs", json=payload)
    assert post_res.status_code == 202
    job_id = post_res.json()["job_id"]

    # Poll until completed
    for _ in range(40):
        status_res = await async_client.get(f"/api/v1/jobs/{job_id}")
        if status_res.json().get("status") == "succeeded":
            break
        await asyncio.sleep(0.1)

    # Save a mock mix.mp3 file to storage for this job
    mock_mp3_content = b"ID3\x03\x00\x00\x00\x00\x00\x00MOCKMP3AUDIOFRAME"
    await storage_service.save_file(job_id, "mix.mp3", mock_mp3_content, "audio/mpeg")

    # Download ZIP
    download_res = await async_client.get(f"/api/v1/jobs/{job_id}/download")
    assert download_res.status_code == 200

    with zipfile.ZipFile(io.BytesIO(download_res.content), "r") as zf:
        namelist = zf.namelist()
        assert "mix.wav" in namelist
        assert "mix.mp3" in namelist
        assert zf.read("mix.mp3") == mock_mp3_content
        assert "music_manifest.json" in namelist
        assert any(n.startswith("stems/") for n in namelist)


@pytest.mark.asyncio
async def test_zip_download_queued_job_returns_409(async_client: AsyncClient):
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        request=MusicJobRequest(prompt="Queued music job", duration_s=10.0),
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    await job_store.create_job(job)

    res = await async_client.get(f"/api/v1/jobs/{job_id}/download")
    assert res.status_code == 409
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "JOB_NOT_READY"
    assert "in progress" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_zip_download_running_job_returns_409(async_client: AsyncClient):
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        request=MusicJobRequest(prompt="Running music job", duration_s=10.0),
        status=JobStatus.RUNNING,
        progress=0.45,
    )
    await job_store.create_job(job)

    res = await async_client.get(f"/api/v1/jobs/{job_id}/download")
    assert res.status_code == 409
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "JOB_NOT_READY"
    assert "in progress" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_zip_download_failed_job_returns_error(async_client: AsyncClient):
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        request=MusicJobRequest(prompt="Failed music job", duration_s=10.0),
        status=JobStatus.FAILED,
        progress=0.30,
        error="Synthesis pipeline crashed during waveform generation",
    )
    await job_store.create_job(job)

    res = await async_client.get(f"/api/v1/jobs/{job_id}/download")
    assert res.status_code == 409
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "JOB_FAILED"
    assert "failed" in data["error"]["message"].lower()
    assert "synthesis pipeline crashed" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_zip_download_nonexistent_job_returns_404(async_client: AsyncClient):
    missing_id = "00000000-0000-0000-0000-000000000000"
    res = await async_client.get(f"/api/v1/jobs/{missing_id}/download")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert missing_id in data["error"]["message"]


@pytest.mark.asyncio
async def test_zip_download_missing_artifacts_returns_404(async_client: AsyncClient):
    # Job is marked succeeded in store, but no files exist on disk
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        request=MusicJobRequest(prompt="Ghost job with no files", duration_s=5.0),
        status=JobStatus.SUCCEEDED,
        progress=1.0,
        result=JobResultSchema(
            audio_url=f"/api/v1/jobs/{job_id}/artifacts/mix.wav",
            stems={"bass": f"/api/v1/jobs/{job_id}/artifacts/stem_bass.wav"},
            manifest_url=f"/api/v1/jobs/{job_id}/artifacts/music_manifest.json",
            duration_s=5.0,
            sample_rate=44100,
            channels=1,
            format="wav",
            stem_gains={"bass": 0.5},
        ),
    )
    await job_store.create_job(job)

    res = await async_client.get(f"/api/v1/jobs/{job_id}/download")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "not found" in data["error"]["message"].lower()
