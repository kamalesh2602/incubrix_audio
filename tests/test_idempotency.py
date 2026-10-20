import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_idempotent_post_returns_existing_job(async_client: AsyncClient):
    key = "test-idempotency-key-001"
    payload = {
        "prompt": "Ambient guitar chords and soft bass",
        "duration_s": 5.0,
    }

    # First request
    res1 = await async_client.post(
        "/api/v1/music/jobs",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert res1.status_code == 202
    data1 = res1.json()
    job_id_1 = data1["job_id"]

    # Immediate second request with the same Idempotency-Key
    res2 = await async_client.post(
        "/api/v1/music/jobs",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert res2.status_code in (200, 202)
    assert res2.headers.get("Idempotent-Replay") == "true"
    data2 = res2.json()
    assert data2["job_id"] == job_id_1

    # Wait for the job to complete
    for _ in range(30):
        check = await async_client.get(f"/api/v1/jobs/{job_id_1}")
        if check.json().get("status") == "succeeded":
            break
        await asyncio.sleep(0.1)

    # Third request after completion
    res3 = await async_client.post(
        "/api/v1/music/jobs",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert res3.status_code == 200
    assert res3.headers.get("Idempotent-Replay") == "true"
    data3 = res3.json()
    assert data3["job_id"] == job_id_1


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_different_jobs(async_client: AsyncClient):
    payload = {
        "prompt": "Ambient synth pad",
        "duration_s": 5.0,
    }

    res1 = await async_client.post(
        "/api/v1/music/jobs",
        json=payload,
        headers={"Idempotency-Key": "key-alpha"},
    )
    assert res1.status_code == 202
    id1 = res1.json()["job_id"]

    res2 = await async_client.post(
        "/api/v1/music/jobs",
        json=payload,
        headers={"Idempotency-Key": "key-beta"},
    )
    assert res2.status_code == 202
    id2 = res2.json()["job_id"]

    assert id1 != id2
