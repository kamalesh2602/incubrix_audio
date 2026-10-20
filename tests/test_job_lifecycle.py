import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_job_submission_and_completion(async_client: AsyncClient):
    payload = {
        "prompt": "Relaxing lo-fi study beats with gentle chords and smooth bass",
        "duration_s": 5.0,
        "tempo_bpm": 90,
        "key": "C major",
        "loopable": True,
        "output": {
            "sample_rate": 44100,
            "target_lufs": -14.0,
            "formats": ["wav"],
        },
    }

    # 1. Submit job
    post_res = await async_client.post("/api/v1/music/jobs", json=payload)
    assert post_res.status_code == 202
    post_data = post_res.json()
    assert "job_id" in post_data
    assert post_data["status"] == "queued"
    assert "job_url" in post_data
    job_id = post_data["job_id"]

    # 2. Poll until succeeded
    completed = False
    for _ in range(30):
        get_res = await async_client.get(f"/api/v1/jobs/{job_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["job_id"] == job_id
        if get_data["status"] == "succeeded":
            completed = True
            break
        await asyncio.sleep(0.1)

    assert completed, "Job did not complete within the allotted timeout"

    # 3. Verify successful response structure
    assert get_data["progress"] == 1.0
    assert get_data["error"] is None
    result = get_data["result"]
    assert result is not None
    assert result["audio_url"].endswith("mix.wav")
    assert result["manifest_url"].endswith("music_manifest.json")
    assert "bass" in result["stems"]
    assert "chords" in result["stems"]
    assert "melody" in result["stems"]
    assert result["duration_s"] == 5.0
    assert result["sample_rate"] == 44100
    assert result["format"] == "wav"

    # 4. Verify artifact download links are real and functional
    mix_res = await async_client.get(result["audio_url"])
    assert mix_res.status_code == 200
    assert mix_res.headers.get("content-type") == "audio/wav"
    assert len(mix_res.content) > 0

    for stem_name, stem_url in result["stems"].items():
        stem_res = await async_client.get(stem_url)
        assert stem_res.status_code == 200
        assert stem_res.headers.get("content-type") == "audio/wav"
        assert len(stem_res.content) > 0

    manifest_res = await async_client.get(result["manifest_url"])
    assert manifest_res.status_code == 200
    assert manifest_res.headers.get("content-type") == "application/json"
    manifest_json = manifest_res.json()
    assert manifest_json["job_id"] == job_id
    assert manifest_json["request"]["prompt"] == payload["prompt"]


@pytest.mark.asyncio
async def test_get_nonexistent_job(async_client: AsyncClient):
    response = await async_client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_nonexistent_artifact(async_client: AsyncClient):
    response = await async_client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000/artifacts/missing.wav")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
