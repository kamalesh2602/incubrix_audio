import array
import io
import math
import wave
import zipfile
import pytest
import httpx

from app.core.config import settings
from app.models.schemas import MusicJobRequest, OutputSchema, SectionSchema
from app.services.audio_normalizer import (
    inspect_and_extract_stem_archive,
    measure_stem_reconstruction_error,
    normalize_audio_to_wav,
)
from app.services.provider import MockMusicProvider, get_music_provider
from app.services.soundverse_adapter import (
    SoundverseAPIError,
    SoundverseClient,
    SoundverseProvider,
)


def create_sine_wav_bytes(freq: float = 440.0, duration_s: float = 1.0, sample_rate: int = 44100) -> bytes:
    """Helper creating valid 16-bit PCM WAV bytes for testing."""
    n_samples = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        samples = [
            int(16000 * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
            for i in range(n_samples)
        ]
        w.writeframes(array.array("h", samples).tobytes())
    return buf.getvalue()


def create_mock_zip_archive(stems_dict: dict) -> bytes:
    """Helper packaging stem WAV bytes into a zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in stems_dict.items():
            zf.writestr(f"stem_{name}.wav", data)
    return buf.getvalue()


def test_soundverse_prompt_construction():
    provider = SoundverseProvider(SoundverseClient(api_key="test-key"))
    req = MusicJobRequest(
        prompt="Dreamy ambient soundscape",
        duration_s=10.0,
        tempo_bpm=80,
        key="D minor",
        sections=[
            SectionSchema(name="intro", start_s=0.0, end_s=4.0),
            SectionSchema(name="main", start_s=4.0, end_s=10.0),
        ],
    )
    composed = provider._build_prompt(req)
    assert "Dreamy ambient soundscape" in composed
    assert "tempo 80 BPM" in composed
    assert "key of D minor" in composed
    assert "intro (0.0s-4.0s)" in composed
    assert "main (4.0s-10.0s)" in composed
    assert "strictly no vocals, no singing, no spoken words" in composed


@pytest.mark.asyncio
async def test_soundverse_missing_api_key_raises_error():
    client = SoundverseClient(api_key="")
    provider = SoundverseProvider(client)
    req = MusicJobRequest(prompt="Jazz piano", duration_s=5.0)
    with pytest.raises(ValueError, match="SOUNDVERSE_API_KEY is not configured"):
        await provider.generate_music("job-test-key", req)


@pytest.mark.asyncio
async def test_soundverse_successful_generation_and_stem_separation():
    mix_wav = create_sine_wav_bytes(freq=220.0, duration_s=2.0, sample_rate=44100)
    bass_wav = create_sine_wav_bytes(freq=80.0, duration_s=2.0, sample_rate=44100)
    drums_wav = create_sine_wav_bytes(freq=150.0, duration_s=2.0, sample_rate=44100)
    piano_wav = create_sine_wav_bytes(freq=440.0, duration_s=2.0, sample_rate=44100)
    guitar_wav = create_sine_wav_bytes(freq=660.0, duration_s=2.0, sample_rate=44100)
    other_wav = create_sine_wav_bytes(freq=880.0, duration_s=2.0, sample_rate=44100)

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        method = request.method

        if "/v7/generate/music" in url and method == "POST":
            return httpx.Response(201, json={"job_id": "gen-task-100", "status": "queued"})

        if "/v7/status?job_id=gen-task-100" in url and method == "GET":
            return httpx.Response(
                200,
                json={
                    "job_id": "gen-task-100",
                    "status": "completed",
                    "output": {
                        "assets": [{"file_id": "mix-file-id", "url": "https://storage.soundverse.ai/mix.wav"}],
                    },
                },
            )

        if "/v1/files/mix-file-id/download" in url and method == "GET":
            return httpx.Response(200, json={"download_url": "https://storage.soundverse.ai/mix.wav"})

        if url == "https://storage.soundverse.ai/mix.wav" and method == "GET":
            return httpx.Response(200, content=mix_wav, headers={"content-type": "audio/wav"})

        if "/v1/generate/stem-separation/six-stem" in url and method == "POST":
            return httpx.Response(201, json={"job_id": "stem-task-200", "status": "queued"})

        if "/v7/status?job_id=stem-task-200" in url and method == "GET":
            return httpx.Response(
                200,
                json={
                    "job_id": "stem-task-200",
                    "status": "completed",
                    "output": {
                        "assets": [
                            {"file_id": "f-bass", "role": "bass", "name": "stem_bass.wav"},
                            {"file_id": "f-drums", "role": "drums", "name": "stem_drums.wav"},
                            {"file_id": "f-piano", "role": "piano", "name": "stem_piano.wav"},
                            {"file_id": "f-guitar", "role": "guitar", "name": "stem_guitar.wav"},
                            {"file_id": "f-other", "role": "other", "name": "stem_other.wav"},
                        ]
                    },
                },
            )

        if "/v1/files/f-bass/download" in url:
            return httpx.Response(200, json={"download_url": "https://storage.soundverse.ai/bass.wav"})
        if "/v1/files/f-drums/download" in url:
            return httpx.Response(200, json={"download_url": "https://storage.soundverse.ai/drums.wav"})
        if "/v1/files/f-piano/download" in url:
            return httpx.Response(200, json={"download_url": "https://storage.soundverse.ai/piano.wav"})
        if "/v1/files/f-guitar/download" in url:
            return httpx.Response(200, json={"download_url": "https://storage.soundverse.ai/guitar.wav"})
        if "/v1/files/f-other/download" in url:
            return httpx.Response(200, json={"download_url": "https://storage.soundverse.ai/other.wav"})

        stem_audio_map = {
            "https://storage.soundverse.ai/bass.wav": bass_wav,
            "https://storage.soundverse.ai/drums.wav": drums_wav,
            "https://storage.soundverse.ai/piano.wav": piano_wav,
            "https://storage.soundverse.ai/guitar.wav": guitar_wav,
            "https://storage.soundverse.ai/other.wav": other_wav,
        }
        if url in stem_audio_map:
            return httpx.Response(200, content=stem_audio_map[url], headers={"content-type": "audio/wav"})

        return httpx.Response(404, text=f"Not Found: {url}")

    transport = httpx.MockTransport(mock_handler)
    client = SoundverseClient(api_key="sksoundverse_valid_key", poll_interval=0.01, transport=transport)
    provider = SoundverseProvider(client)

    req = MusicJobRequest(
        prompt="Energetic synth funk",
        duration_s=5.0,
        output=OutputSchema(sample_rate=48000),
    )

    artifacts = await provider.generate_music("test-full-flow", req)

    # 1. Output duration and sample rate normalization
    assert artifacts.sample_rate == 48000
    assert artifacts.duration_s == 5.0

    # 2. At least three genuinely separate instrument stems
    assert len(artifacts.stem_bytes) >= 3
    for required_stem in ["bass", "drums", "piano", "guitar"]:
        assert required_stem in artifacts.stem_bytes

    # 3. Honest reconstruction validation
    val = artifacts.manifest_dict["stem_reconstruction_validation"]
    assert "mae" in val
    assert "rmse" in val
    assert "signal_to_error_ratio_db" in val
    assert "nonlinear neural residual reconstruction error" in str(artifacts.manifest_dict["warnings"])

    # 4. Verified rights & licensing disclaimer
    rights = artifacts.manifest_dict["rights_and_licensing"]
    assert rights["commercial_clearance"] is False
    assert rights["verified"] is False
    assert "UNVERIFIED" in rights["notes"]


@pytest.mark.asyncio
async def test_soundverse_zip_archive_stem_handling():
    mix_wav = create_sine_wav_bytes(freq=300.0, duration_s=1.0)
    zip_bytes = create_mock_zip_archive({
        "bass": create_sine_wav_bytes(freq=80.0, duration_s=1.0),
        "drums": create_sine_wav_bytes(freq=120.0, duration_s=1.0),
        "lead": create_sine_wav_bytes(freq=550.0, duration_s=1.0),
    })

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "/generate/music" in url:
            return httpx.Response(201, json={"job_id": "gen-zip", "status": "queued"})
        if "status?job_id=gen-zip" in url:
            return httpx.Response(200, json={"status": "completed", "output": {"audio_url": "https://storage.soundverse.ai/mix.wav"}})
        if url == "https://storage.soundverse.ai/mix.wav":
            return httpx.Response(200, content=mix_wav, headers={"content-type": "audio/wav"})
        if "stem-separation" in url:
            return httpx.Response(201, json={"job_id": "stem-zip", "status": "queued"})
        if "status?job_id=stem-zip" in url:
            return httpx.Response(200, json={"status": "completed", "output": {"assets": [{"file_id": "archive-1", "name": "stems.zip"}]}})
        if "/v1/files/archive-1/download" in url:
            return httpx.Response(200, content=zip_bytes, headers={"content-type": "application/zip"})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = SoundverseClient(api_key="sksoundverse_key", poll_interval=0.01, transport=transport)
    provider = SoundverseProvider(client)

    artifacts = await provider.generate_music("job-zip", MusicJobRequest(prompt="Rock track", duration_s=5.0))
    assert "bass" in artifacts.stem_bytes
    assert "drums" in artifacts.stem_bytes
    assert "lead" in artifacts.stem_bytes
    assert len(artifacts.stem_bytes) >= 3


@pytest.mark.asyncio
async def test_soundverse_rate_limiting_and_retry():
    attempts = 0

    def mock_handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "RateLimited", "message": "Per-tool rate limit exceeded", "retryable": True})
        return httpx.Response(201, json={"job_id": "job-after-retry", "status": "queued"})

    transport = httpx.MockTransport(mock_handler)
    client = SoundverseClient(api_key="key", max_retries=2, retry_backoff=0.01, transport=transport)
    job_id = await client.create_music_generation("ambient", model_version="v7")
    assert job_id == "job-after-retry"
    assert attempts == 2


@pytest.mark.asyncio
async def test_soundverse_non_retryable_provider_error():
    def mock_handler(request: httpx.Request):
        return httpx.Response(402, json={"error": "InsufficientFunds", "message": "Token reservation failed"})

    transport = httpx.MockTransport(mock_handler)
    client = SoundverseClient(api_key="key", max_retries=2, retry_backoff=0.01, transport=transport)
    with pytest.raises(SoundverseAPIError) as exc_info:
        await client.create_music_generation("ambient")
    assert "InsufficientFunds" in str(exc_info.value)
    assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_soundverse_polling_timeout():
    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={"status": "processing"})

    transport = httpx.MockTransport(mock_handler)
    client = SoundverseClient(api_key="key", poll_interval=0.01, poll_timeout=0.05, transport=transport)
    with pytest.raises(TimeoutError, match="timed out"):
        await client.poll_job("timeout-job")


@pytest.mark.asyncio
async def test_soundverse_corrupted_audio_fails_validation():
    with pytest.raises(ValueError, match="Failed to decode audio content"):
        normalize_audio_to_wav(b"not-a-valid-audio-stream", target_duration_s=5.0)


def test_measure_stem_reconstruction_error_metrics():
    # Synthetic test samples
    mix = [1000, 2000, 3000, 4000]
    stems = {
        "stem1": [900, 1900, 2900, 3900],
        "stem2": [50, 50, 50, 50],
    }
    # sum is [950, 1950, 2950, 3950], diff is 50 for all
    res = measure_stem_reconstruction_error(mix, stems)
    assert res["is_exact_reconstruction"] is False
    assert res["mae"] == 50.0
    assert res["rmse"] == 50.0
    assert res["max_error"] == 50
    assert "Residual reconstruction error is present" in res["notes"]


def test_factory_provider_selection(monkeypatch):
    monkeypatch.setattr(settings, "PROVIDER_TYPE", "mock")
    p1 = get_music_provider()
    assert isinstance(p1, MockMusicProvider)

    monkeypatch.setattr(settings, "PROVIDER_TYPE", "soundverse")
    p2 = get_music_provider()
    assert isinstance(p2, SoundverseProvider)
