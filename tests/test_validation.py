import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_prompt(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={"duration_s": 10.0},
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    fields = [d["field"] for d in data["error"]["details"]]
    assert "prompt" in fields


@pytest.mark.asyncio
async def test_empty_prompt(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={"prompt": "   ", "duration_s": 10.0},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    fields = [d["field"] for d in data["error"]["details"]]
    assert "prompt" in fields


@pytest.mark.asyncio
async def test_duration_below_minimum(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={"prompt": "Upbeat synthwave", "duration_s": 4.9},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    fields = [d["field"] for d in data["error"]["details"]]
    assert "duration_s" in fields


@pytest.mark.asyncio
async def test_duration_above_maximum(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={"prompt": "Epic cinematic soundtrack", "duration_s": 300.5},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    fields = [d["field"] for d in data["error"]["details"]]
    assert "duration_s" in fields


@pytest.mark.asyncio
async def test_invalid_tempo_bpm(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={"prompt": "Lo-fi beat", "duration_s": 10.0, "tempo_bpm": 20},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    fields = [d["field"] for d in data["error"]["details"]]
    assert "tempo_bpm" in fields


@pytest.mark.asyncio
async def test_section_start_greater_than_end(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={
            "prompt": "Ambient study music",
            "duration_s": 15.0,
            "sections": [
                {"name": "intro", "start_s": 5.0, "end_s": 2.0},
            ],
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_section_end_exceeds_job_duration(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={
            "prompt": "Ambient study music",
            "duration_s": 10.0,
            "sections": [
                {"name": "intro", "start_s": 0.0, "end_s": 12.0},
            ],
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "exceeds job duration_s" in str(data)


@pytest.mark.asyncio
async def test_overlapping_sections(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={
            "prompt": "Cinematic track",
            "duration_s": 20.0,
            "sections": [
                {"name": "intro", "start_s": 0.0, "end_s": 10.0},
                {"name": "verse", "start_s": 8.0, "end_s": 18.0},
            ],
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "overlaps" in str(data)


@pytest.mark.asyncio
async def test_unsupported_audio_format(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={
            "prompt": "Jazz trio",
            "duration_s": 10.0,
            "output": {"formats": ["flac"]},
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Unsupported format" in str(data)


@pytest.mark.asyncio
async def test_unsupported_sample_rate(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={
            "prompt": "Classical string quartet",
            "duration_s": 10.0,
            "output": {"sample_rate": 96000},
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Unsupported sample rate" in str(data)


@pytest.mark.asyncio
async def test_invalid_narration_url(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/music/jobs",
        json={
            "prompt": "Podcast background",
            "duration_s": 10.0,
            "narration_url": "ftp://not-a-valid-http-url/voice.mp3",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "narration_url" in str(data)
