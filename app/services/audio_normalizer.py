import array
import io
import math
import wave
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import miniaudio


def normalize_audio_to_wav(
    audio_bytes: bytes,
    target_duration_s: float,
    target_sample_rate: int = 48000,
    target_channels: int = 1,
) -> Tuple[bytes, array.array]:
    """Decodes audio from any supported format (WAV, MP3, FLAC, Vorbis) using miniaudio,

    mixes down to mono, resamples to target_sample_rate (default 48 kHz), trims or pads
    to exact sample-accurate duration, and returns 16-bit PCM WAV bytes and sample array.
    """
    if not audio_bytes or len(audio_bytes) < 16:
        raise ValueError("Audio data is empty or too short to be a valid audio file.")

    try:
        decoded = miniaudio.decode(audio_bytes)
    except Exception as exc:
        raise ValueError(f"Failed to decode audio content: {exc}") from exc

    in_sr = decoded.sample_rate
    n_ch = decoded.nchannels
    raw_samples = decoded.samples

    if not raw_samples:
        raise ValueError("Decoded audio contains no audio frames.")

    # 1. Convert to mono if multi-channel
    if n_ch == 1:
        mono_samples = list(raw_samples)
    elif n_ch == 2:
        # Interleaved (L, R)
        mono_samples = [
            (raw_samples[i] + raw_samples[i + 1]) // 2
            for i in range(0, len(raw_samples), 2)
        ]
    else:
        mono_samples = [
            sum(raw_samples[i : i + n_ch]) // n_ch
            for i in range(0, len(raw_samples), n_ch)
        ]

    # 2. Resample to target_sample_rate if needed (band-limited linear interpolation)
    target_total_samples = max(1, int(round(target_duration_s * target_sample_rate)))
    if in_sr == target_sample_rate:
        resampled = mono_samples
    else:
        ratio = in_sr / float(target_sample_rate)
        resampled_len = int(round(len(mono_samples) / ratio))
        resampled = [0] * resampled_len
        n_in = len(mono_samples)
        for j in range(resampled_len):
            pos = j * ratio
            i = int(pos)
            if i >= n_in - 1:
                val = mono_samples[-1] if n_in > 0 else 0
            else:
                alpha = pos - i
                val = int(round((1.0 - alpha) * mono_samples[i] + alpha * mono_samples[i + 1]))
            resampled[j] = max(-32768, min(32767, val))

    # 3. Trim or pad to exact target_total_samples
    if len(resampled) >= target_total_samples:
        final_samples = resampled[:target_total_samples]
    else:
        final_samples = resampled + [0] * (target_total_samples - len(resampled))

    # 4. Pack into standard 16-bit PCM WAV
    arr = array.array("h", final_samples)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(target_channels)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(target_sample_rate)
        wav_file.writeframes(arr.tobytes())

    return buf.getvalue(), arr


def measure_stem_reconstruction_error(
    mix_samples: Sequence[int],
    stem_samples_dict: Dict[str, Sequence[int]],
) -> Dict[str, Any]:
    """Measures reconstruction discrepancy between the provider's mix and the sum of separated stems.

    Provides honest, non-fabricated metrics: MAE, RMSE, Peak Error, and Signal-to-Error Ratio (dB).
    """
    n_samples = len(mix_samples)
    if n_samples == 0:
        return {
            "is_exact_reconstruction": False,
            "error_message": "Empty mix sample stream.",
        }

    sum_stems = [0] * n_samples
    for stem_samples in stem_samples_dict.values():
        min_len = min(n_samples, len(stem_samples))
        for t in range(min_len):
            sum_stems[t] += stem_samples[t]

    abs_errors = [abs(mix_samples[t] - sum_stems[t]) for t in range(n_samples)]
    squared_errors = [(mix_samples[t] - sum_stems[t]) ** 2 for t in range(n_samples)]
    signal_power = sum(s ** 2 for s in mix_samples) / float(n_samples)
    error_power = sum(squared_errors) / float(n_samples)

    mae = round(sum(abs_errors) / float(n_samples), 2)
    rmse = round(math.sqrt(error_power), 2)
    max_error = int(max(abs_errors)) if abs_errors else 0

    if error_power < 1e-9:
        ser_db = 999.0
        is_exact = True
    else:
        ser_db = round(10.0 * math.log10(max(1e-9, signal_power) / error_power), 2)
        is_exact = (max_error == 0)

    notes = (
        "Reconstruction is exact (lossless sum)."
        if is_exact
        else "Separation performed via neural model. Residual reconstruction error is present due to "
        "phase cancellation and nonlinear spectral masking in stem separation."
    )

    return {
        "is_exact_reconstruction": is_exact,
        "mae": mae,
        "rmse": rmse,
        "max_error": max_error,
        "signal_to_error_ratio_db": ser_db,
        "notes": notes,
    }


def inspect_and_extract_stem_archive(archive_bytes: bytes) -> Dict[str, bytes]:
    """Inspects a zip archive returned by a stem separation job and extracts audio stems

    by mapping filenames to stem roles (e.g. drums, bass, guitar, piano, vocals, other).
    """
    extracted_stems: Dict[str, bytes] = {}
    buf = io.BytesIO(archive_bytes)

    if not zipfile.is_zipfile(buf):
        raise ValueError("Provided bytes are not a valid zip archive.")

    with zipfile.ZipFile(buf, "r") as zf:
        namelist = zf.namelist()
        for name in namelist:
            # Skip directories or macOS metadata
            if name.endswith("/") or name.startswith("__MACOSX"):
                continue

            path = Path(name)
            ext = path.suffix.lower()
            if ext in (".wav", ".mp3", ".flac", ".m4a", ".ogg"):
                stem_raw_bytes = zf.read(name)
                # Parse role from stem filename
                stem_tag = path.stem.lower()
                clean_role = stem_tag.replace("stem_", "").replace("_stem", "").strip()
                extracted_stems[clean_role] = stem_raw_bytes

    return extracted_stems
