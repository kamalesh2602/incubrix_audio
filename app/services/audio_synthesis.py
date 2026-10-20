import array
import io
import math
import random
import wave
from typing import Dict, List, Optional, Tuple

from app.models.schemas import SectionSchema

STEM_GAINS: Dict[str, float] = {
    "bass": 0.35,
    "chords": 0.30,
    "melody": 0.35,
}

STEM_NAMES: List[str] = ["bass", "chords", "melody"]

# Mapping of standard musical key names to root MIDI note and scale intervals
KEY_MAP: Dict[str, Tuple[int, List[int]]] = {
    "c major": (60, [0, 2, 4, 5, 7, 9, 11]),
    "c minor": (60, [0, 2, 3, 5, 7, 8, 10]),
    "c# major": (61, [0, 2, 4, 5, 7, 9, 11]),
    "c# minor": (61, [0, 2, 3, 5, 7, 8, 10]),
    "d major": (62, [0, 2, 4, 5, 7, 9, 11]),
    "d minor": (62, [0, 2, 3, 5, 7, 8, 10]),
    "eb major": (63, [0, 2, 4, 5, 7, 9, 11]),
    "eb minor": (63, [0, 2, 3, 5, 7, 8, 10]),
    "e major": (64, [0, 2, 4, 5, 7, 9, 11]),
    "e minor": (64, [0, 2, 3, 5, 7, 8, 10]),
    "f major": (65, [0, 2, 4, 5, 7, 9, 11]),
    "f minor": (65, [0, 2, 3, 5, 7, 8, 10]),
    "f# major": (66, [0, 2, 4, 5, 7, 9, 11]),
    "f# minor": (66, [0, 2, 3, 5, 7, 8, 10]),
    "g major": (67, [0, 2, 4, 5, 7, 9, 11]),
    "g minor": (67, [0, 2, 3, 5, 7, 8, 10]),
    "ab major": (68, [0, 2, 4, 5, 7, 9, 11]),
    "ab minor": (68, [0, 2, 3, 5, 7, 8, 10]),
    "a major": (69, [0, 2, 4, 5, 7, 9, 11]),
    "a minor": (69, [0, 2, 3, 5, 7, 8, 10]),
    "bb major": (70, [0, 2, 4, 5, 7, 9, 11]),
    "bb minor": (70, [0, 2, 3, 5, 7, 8, 10]),
    "b major": (71, [0, 2, 4, 5, 7, 9, 11]),
    "b minor": (71, [0, 2, 3, 5, 7, 8, 10]),
}


def midi_to_frequency(midi_note: float) -> float:
    """Converts a MIDI note number to frequency in Hertz."""
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


def samples_to_wav_bytes(samples: array.array, sample_rate: int, channels: int = 1) -> bytes:
    """Encodes a signed 16-bit integer array into standard PCM WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit PCM (2 bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    return buf.getvalue()


def read_wav_samples(wav_bytes: bytes) -> Tuple[List[int], int, int]:
    """Decodes standard PCM WAV bytes into a list of 16-bit integer samples.

    Returns:
        (samples, sample_rate, channels)
    """
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sampwidth = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        nframes = wav_file.getnframes()
        frames = wav_file.readframes(nframes)

        if sampwidth != 2:
            raise ValueError(f"Expected 16-bit PCM audio, got sample width {sampwidth}")

        arr = array.array("h")
        arr.frombytes(frames)
        return arr.tolist(), sample_rate, channels


def synthesize_deterministic_stems(
    duration_s: float,
    sample_rate: int = 44100,
    tempo_bpm: int = 120,
    key_name: Optional[str] = "C major",
    seed: int = 42,
    sections: Optional[List[SectionSchema]] = None,
) -> Tuple[Dict[str, array.array], array.array, Dict[str, float]]:
    """Synthesizes three genuinely separate instrument stems (bass, chords, melody)

    and the full mix deterministically for the given duration and parameters.

    Returns:
        stems: Dict[str, array.array] of 16-bit integer arrays
        mix: array.array of 16-bit integer array
        gains: Dict[str, float] documented mixing gains
    """
    total_samples = int(round(duration_s * sample_rate))
    rng = random.Random(seed)

    # Resolve key and scale
    norm_key = (key_name or "C major").strip().lower()
    if norm_key in KEY_MAP:
        root_midi, scale_intervals = KEY_MAP[norm_key]
    else:
        root_midi, scale_intervals = KEY_MAP["c major"]

    beat_duration = 60.0 / float(tempo_bpm)
    samples_per_beat = max(1, int(round(beat_duration * sample_rate)))

    # Chord progression (Roman numerals: I - V - vi - IV or similar in scale degrees)
    progression = [0, 4, 5, 3]

    bass_samples = array.array("h", [0] * total_samples)
    chord_samples = array.array("h", [0] * total_samples)
    melody_samples = array.array("h", [0] * total_samples)
    mix_samples = array.array("h", [0] * total_samples)

    num_beats = int(math.ceil(duration_s / beat_duration))

    for beat_idx in range(num_beats):
        prog_step = progression[(beat_idx // 2) % len(progression)]
        chord_root_interval = scale_intervals[prog_step % len(scale_intervals)]

        # 1. Bass instrument: deep fundamental + 2nd harmonic, low register (MIDI ~36-48)
        bass_midi = root_midi - 24 + chord_root_interval
        bass_freq = midi_to_frequency(bass_midi)

        # 2. Chords instrument: triad voicing in middle register (MIDI ~48-60)
        c3_idx = (prog_step + 2) % len(scale_intervals)
        c5_idx = (prog_step + 4) % len(scale_intervals)
        chord_freqs = [
            midi_to_frequency(root_midi - 12 + chord_root_interval),
            midi_to_frequency(root_midi - 12 + scale_intervals[c3_idx]),
            midi_to_frequency(root_midi - 12 + scale_intervals[c5_idx]),
        ]

        # 3. Melody instrument: upper register lead note with musical variations
        mel_interval = rng.choice(scale_intervals)
        mel_midi = root_midi + mel_interval
        mel_freq = midi_to_frequency(mel_midi)

        start_samp = beat_idx * samples_per_beat
        end_samp = min((beat_idx + 1) * samples_per_beat, total_samples)
        beat_len = end_samp - start_samp
        if beat_len <= 0:
            break

        for i in range(beat_len):
            t = i / float(sample_rate)
            idx = start_samp + i

            # Bass: punchy exponential decay envelope with solid low frequencies
            b_env = math.exp(-3.0 * (i / samples_per_beat))
            b_val = math.sin(2.0 * math.pi * bass_freq * t) + 0.35 * math.sin(4.0 * math.pi * bass_freq * t)
            b_int = int(round(25000 * b_env * b_val * 0.75))
            bass_samples[idx] = max(-32768, min(32767, b_int))

            # Chords: warm synth pad with gentle attack and sustained polyphony
            c_env = 0.5 * (1.0 - math.cos(math.pi * min(1.0, i / (0.1 * sample_rate)))) if i < 0.1 * sample_rate else 1.0
            c_val = sum(math.sin(2.0 * math.pi * f * t) for f in chord_freqs) / 3.0
            c_int = int(round(23000 * c_env * c_val * 0.75))
            chord_samples[idx] = max(-32768, min(32767, c_int))

            # Melody: expressive lead voice with subtle vibrato
            vibrato = 1.0 + 0.008 * math.sin(2.0 * math.pi * 5.5 * t)
            m_env = math.exp(-1.8 * (i / samples_per_beat))
            m_val = math.sin(2.0 * math.pi * mel_freq * vibrato * t)
            m_int = int(round(24000 * m_env * m_val * 0.75))
            melody_samples[idx] = max(-32768, min(32767, m_int))

            # Mix reconstruction formula: exact weighted sum with documented gains
            mix_val = int(round(
                STEM_GAINS["bass"] * bass_samples[idx] +
                STEM_GAINS["chords"] * chord_samples[idx] +
                STEM_GAINS["melody"] * melody_samples[idx]
            ))
            mix_samples[idx] = max(-32768, min(32767, mix_val))

    stems = {
        "bass": bass_samples,
        "chords": chord_samples,
        "melody": melody_samples,
    }
    return stems, mix_samples, STEM_GAINS
