import io
import math
import wave
import pytest
from httpx import AsyncClient

from app.services.audio_synthesis import (
    STEM_GAINS,
    read_wav_samples,
    synthesize_deterministic_stems,
)


def compute_rms(samples: list) -> float:
    """Calculates Root Mean Square amplitude of audio samples."""
    if not samples:
        return 0.0
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / len(samples))


def count_zero_crossings(samples: list) -> int:
    """Counts the number of zero-crossings in an audio signal to estimate fundamental pitch register."""
    crossings = 0
    for i in range(1, len(samples)):
        if (samples[i - 1] < 0 and samples[i] >= 0) or (samples[i - 1] >= 0 and samples[i] < 0):
            crossings += 1
    return crossings


@pytest.mark.parametrize("duration_s", [5.0, 7.5, 12.0])
def test_exact_audio_duration_across_sample_rates(duration_s: float):
    sample_rate = 44100
    expected_samples = int(round(duration_s * sample_rate))

    stems, mix, gains = synthesize_deterministic_stems(
        duration_s=duration_s,
        sample_rate=sample_rate,
        tempo_bpm=120,
        seed=123,
    )

    # 1. Check array length
    assert len(mix) == expected_samples, f"Mix sample count mismatch for duration {duration_s}s"
    for stem_name, stem_samples in stems.items():
        assert len(stem_samples) == expected_samples, f"Stem '{stem_name}' sample count mismatch"

    # 2. Check duration when encoded and decoded as WAV
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(mix.tobytes())

    buf.seek(0)
    with wave.open(buf, "rb") as r:
        nframes = r.getnframes()
        framerate = r.getframerate()
        assert nframes == expected_samples
        assert nframes / float(framerate) == duration_s


def test_genuinely_separate_stems_and_no_silence():
    duration_s = 6.0
    sample_rate = 44100
    stems, mix, _ = synthesize_deterministic_stems(
        duration_s=duration_s,
        sample_rate=sample_rate,
        tempo_bpm=120,
        seed=42,
    )

    bass = stems["bass"]
    chords = stems["chords"]
    melody = stems["melody"]

    # 1. No stem or mix should be silent
    assert compute_rms(bass) > 500.0, "Bass stem is silent or too quiet"
    assert compute_rms(chords) > 500.0, "Chords stem is silent or too quiet"
    assert compute_rms(melody) > 500.0, "Melody stem is silent or too quiet"
    assert compute_rms(mix) > 500.0, "Mix is silent or too quiet"

    # 2. Stems must not be identical copies
    assert list(bass) != list(chords), "Bass and Chords stems are identical"
    assert list(bass) != list(melody), "Bass and Melody stems are identical"
    assert list(chords) != list(melody), "Chords and Melody stems are identical"

    # 3. Frequency separation: bass should have substantially lower pitch / fewer zero crossings than melody
    bass_zc = count_zero_crossings(list(bass))
    melody_zc = count_zero_crossings(list(melody))
    assert melody_zc > 2.0 * bass_zc, (
        f"Expected melody zero crossings ({melody_zc}) to be substantially higher than bass ({bass_zc})"
    )


def test_mathematical_mix_reconstruction_from_stems():
    duration_s = 5.0
    sample_rate = 44100
    stems, mix, gains = synthesize_deterministic_stems(
        duration_s=duration_s,
        sample_rate=sample_rate,
        tempo_bpm=120,
        seed=999,
    )

    bass = list(stems["bass"])
    chords = list(stems["chords"])
    melody = list(stems["melody"])
    mix_list = list(mix)

    reconstructed = []
    for i in range(len(mix_list)):
        val = int(round(
            gains["bass"] * bass[i] +
            gains["chords"] * chords[i] +
            gains["melody"] * melody[i]
        ))
        clamped = max(-32768, min(32767, val))
        reconstructed.append(clamped)

    diffs = [abs(m - r) for m, r in zip(mix_list, reconstructed)]
    max_diff = max(diffs)
    assert max_diff == 0, f"Mix reconstruction failed with max diff {max_diff}"
    assert mix_list == reconstructed, "Reconstructed mix does not exactly match exported mix"


def test_seed_determinism():
    stems1, mix1, _ = synthesize_deterministic_stems(5.0, seed=777)
    stems2, mix2, _ = synthesize_deterministic_stems(5.0, seed=777)

    assert list(mix1) == list(mix2), "Identical seeds produced different mixes"
    for stem_name in ["bass", "chords", "melody"]:
        assert list(stems1[stem_name]) == list(stems2[stem_name]), (
            f"Identical seeds produced different {stem_name} stems"
        )
