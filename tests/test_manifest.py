import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_music_manifest_contents_and_licensing(async_client: AsyncClient):
    payload = {
        "prompt": "Cinematic ambient background music with warm chords",
        "duration_s": 5.0,
        "seed": 4242,
        "tempo_bpm": 110,
        "key": "A minor",
        "output": {
            "sample_rate": 44100,
            "target_lufs": -14.0,
            "formats": ["wav"],
        },
    }

    post_res = await async_client.post("/api/v1/music/jobs", json=payload)
    assert post_res.status_code == 202
    job_id = post_res.json()["job_id"]

    # Poll for completion
    for _ in range(30):
        get_res = await async_client.get(f"/api/v1/jobs/{job_id}")
        if get_res.json().get("status") == "succeeded":
            break
        await asyncio.sleep(0.1)

    result = get_res.json()["result"]
    manifest_res = await async_client.get(result["manifest_url"])
    assert manifest_res.status_code == 200
    manifest = manifest_res.json()

    # 1. Manifest structure verification
    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["job_id"] == job_id
    assert manifest["seed"] == 4242

    # 2. Request verification
    assert manifest["request"]["prompt"] == payload["prompt"]
    assert manifest["request"]["duration_s"] == 5.0

    # 3. Provider verification
    assert manifest["provider"]["name"] == "MockMusicProvider"
    assert manifest["provider"]["version"] == "1.0.0"
    assert manifest["provider"]["type"] == "mock"

    # 4. Settings verification
    assert manifest["settings"]["sample_rate"] == 44100
    assert manifest["settings"]["channels"] == 1
    assert manifest["settings"]["bit_depth"] == 16
    assert manifest["settings"]["format"] == "pcm_s16le"
    assert manifest["settings"]["target_lufs"] == -14.0

    # 5. Stems and gains
    assert "bass" in manifest["stem_filenames"]
    assert "chords" in manifest["stem_filenames"]
    assert "melody" in manifest["stem_filenames"]
    assert manifest["mix_filename"] == "mix.wav"

    gains = manifest["stem_gains"]
    assert "bass" in gains
    assert "chords" in gains
    assert "melody" in gains
    assert sum(gains.values()) <= 1.0
    assert "reconstruction_formula" in manifest

    # 6. Duration & Timings
    assert manifest["duration"]["requested_s"] == 5.0
    assert manifest["duration"]["actual_s"] == 5.0
    assert manifest["duration"]["total_samples"] == 44100 * 5
    assert manifest["sample_rate"] == 44100
    assert "created_at" in manifest["timings"]
    assert "completed_at" in manifest["timings"]
    assert manifest["timings"]["generation_time_s"] >= 0.0

    # 7. Warnings
    assert isinstance(manifest["warnings"], list)
    assert len(manifest["warnings"]) > 0

    # 8. Rights and Licensing (CRITICAL: Never claim commercial clearance without verification)
    rights = manifest["rights_and_licensing"]
    assert rights["commercial_clearance"] is False
    assert rights["status"] == "unverified_mock_synthesis"
    assert "commercial clearance" in rights["notes"].lower()
