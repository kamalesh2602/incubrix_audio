import json
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from app.core.config import settings
from app.models.schemas import MusicJobRequest
from app.services.audio_synthesis import (
    samples_to_wav_bytes,
    synthesize_deterministic_stems,
)


@dataclass
class GenerationArtifacts:
    mix_bytes: bytes
    stem_bytes: Dict[str, bytes]
    manifest_dict: Dict[str, Any]
    manifest_bytes: bytes
    stem_filenames: Dict[str, str]
    mix_filename: str
    manifest_filename: str
    duration_s: float
    sample_rate: int
    stem_gains: Dict[str, float]


class MusicProvider(ABC):
    """Abstract provider interface for music generation engines.

    Allows plugging in external models, cloud AI providers, or local neural engines
    without modifying job orchestration or API endpoints.
    """

    name: str = "BaseMusicProvider"
    version: str = "0.1.0"

    @abstractmethod
    async def generate_music(
        self,
        job_id: str,
        request: MusicJobRequest,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> GenerationArtifacts:
        """Executes music synthesis and returns all generated audio artifacts and manifest."""
        pass


class MockMusicProvider(MusicProvider):
    """Deterministic, configurable mock music provider synthesizing valid WAV audio

    with three genuinely separate stems (bass, chords, melody) and a mathematically
    reconstructible mix.
    """

    name: str = "MockMusicProvider"
    version: str = "1.0.0"

    async def generate_music(
        self,
        job_id: str,
        request: MusicJobRequest,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> GenerationArtifacts:
        t0 = time.time()
        start_dt = datetime.now(timezone.utc)

        if progress_callback:
            await progress_callback(0.2)

        # Deterministic seed resolution: use provided seed, or derive deterministically from prompt
        if request.seed is not None:
            active_seed = request.seed
        else:
            # Deterministic hash of prompt so repeating without seed is also reproducible
            active_seed = abs(hash(request.prompt)) % (2**31)

        sample_rate = (
            request.output.sample_rate
            if (request.output and request.output.sample_rate)
            else settings.DEFAULT_SAMPLE_RATE
        )
        tempo = request.tempo_bpm or settings.DEFAULT_TEMPO_BPM
        key = request.key or settings.DEFAULT_KEY

        # Synthesize stems and mix
        stems, mix_samples, stem_gains = synthesize_deterministic_stems(
            duration_s=request.duration_s,
            sample_rate=sample_rate,
            tempo_bpm=tempo,
            key_name=key,
            seed=active_seed,
            sections=request.sections,
        )

        if progress_callback:
            await progress_callback(0.5)

        # Encode to 16-bit PCM WAV
        stem_bytes: Dict[str, bytes] = {}
        stem_filenames: Dict[str, str] = {}
        for stem_name, samples in stems.items():
            filename = f"stem_{stem_name}.wav"
            stem_filenames[stem_name] = filename
            stem_bytes[stem_name] = samples_to_wav_bytes(samples, sample_rate, channels=1)

        mix_filename = "mix.wav"
        mix_bytes = samples_to_wav_bytes(mix_samples, sample_rate, channels=1)

        if progress_callback:
            await progress_callback(0.8)

        end_dt = datetime.now(timezone.utc)
        elapsed_s = round(time.time() - t0, 4)
        actual_duration_s = round(len(mix_samples) / float(sample_rate), 4)

        # Build music_manifest.json
        manifest_dict: Dict[str, Any] = {
            "manifest_version": "1.0.0",
            "job_id": job_id,
            "request": request.model_dump(mode="json"),
            "seed": active_seed,
            "provider": {
                "name": self.name,
                "version": self.version,
                "type": "mock",
                "description": "Deterministic multi-stem algorithmic oscillator mock provider",
            },
            "settings": {
                "sample_rate": sample_rate,
                "channels": 1,
                "bit_depth": 16,
                "format": "pcm_s16le",
                "target_lufs": (
                    request.output.target_lufs
                    if request.output
                    else settings.DEFAULT_TARGET_LUFS
                ),
            },
            "stem_filenames": stem_filenames,
            "mix_filename": mix_filename,
            "stem_gains": stem_gains,
            "reconstruction_formula": (
                "mix[t] = clamp(round(gain_bass * stem_bass[t] + "
                "gain_chords * stem_chords[t] + gain_melody * stem_melody[t]), -32768, 32767)"
            ),
            "duration": {
                "requested_s": request.duration_s,
                "actual_s": actual_duration_s,
                "total_samples": len(mix_samples),
            },
            "sample_rate": sample_rate,
            "timings": {
                "created_at": start_dt.isoformat(),
                "completed_at": end_dt.isoformat(),
                "generation_time_s": elapsed_s,
                "section_timings": [sec.model_dump() for sec in (request.sections or [])],
            },
            "warnings": [
                "Generated using local synthetic mock provider for testing and development.",
                "In-memory job storage: job metadata and audio stems will not persist across server restarts.",
                "Audio is algorithmically generated using sinusoidal/harmonic synthesis; not produced by deep generative AI models.",
            ],
            "rights_and_licensing": {
                "status": "unverified_mock_synthesis",
                "commercial_clearance": False,
                "license_type": "development_and_testing_only",
                "notes": (
                    "Generated with local algorithmic oscillator synthesis mock provider. "
                    "Commercial clearance has NOT been verified. Never claim commercial clearance without verification."
                ),
            },
        }

        manifest_bytes = json.dumps(manifest_dict, indent=2).encode("utf-8")
        manifest_filename = "music_manifest.json"

        if progress_callback:
            await progress_callback(0.9)

        return GenerationArtifacts(
            mix_bytes=mix_bytes,
            stem_bytes=stem_bytes,
            manifest_dict=manifest_dict,
            manifest_bytes=manifest_bytes,
            stem_filenames=stem_filenames,
            mix_filename=mix_filename,
            manifest_filename=manifest_filename,
            duration_s=actual_duration_s,
            sample_rate=sample_rate,
            stem_gains=stem_gains,
        )


def get_music_provider() -> MusicProvider:
    """Factory returning configured music provider based on PROVIDER_TYPE setting."""
    if settings.PROVIDER_TYPE.lower() == "soundverse":
        from app.services.soundverse_adapter import SoundverseProvider
        return SoundverseProvider()
    return MockMusicProvider()
