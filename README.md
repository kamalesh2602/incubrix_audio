# IncuBrix AI Background Music Engine (Phase 1)

Welcome to Phase 1 of the **IncuBrix AI Background Music Engine**, a modular, asynchronous FastAPI service designed for generating structured background music with separated instrument stems, deterministic playback, and automated manifest creation.

---

> [!WARNING]
> **IMPORTANT ARCHITECTURAL NOTICE — NOT PRODUCTION READY**
> For this Phase 1 milestone, background jobs execute in-process and state is held in an **in-memory store** (`InMemoryJobStore`).
> **In-memory jobs do NOT survive server restarts or process crashes**, and cannot be shared across multiple horizontal worker processes.
> This setup is intended strictly for local development, interface validation, and automated testing. Production deployment requires replacing these components with PostgreSQL, Redis, and MinIO/S3 (see [Production Transition Roadmap](#production-transition-roadmap)).

---

## Key Features

1. **Robust Request/Response Validation**:
   - `POST /api/v1/music/jobs` validated with Pydantic schemas.
   - Validates duration (5 to 300 seconds), prompt presence, tempo (30–300 BPM), musical key, loopable flag, narration URL, and section timestamps.
   - Validates supported audio formats (`wav`) and sample rates (22,050 Hz, 44,100 Hz, 48,000 Hz).
   - Uniform JSON error responses across all validation and HTTP failure modes: `{"error": {"code": "...", "message": "...", "details": [...]}}`.

2. **Provider Abstraction & Deterministic Mock Provider**:
   - `MusicProvider` interface cleanly separates generation logic from web routing.
   - `MockMusicProvider` generates real, deterministic, 16-bit PCM WAV audio.
   - Generates three genuinely separate synthesized instrument parts:
     - **Bass**: Low-register fundamental frequencies (40–120 Hz) with punchy ADSR envelope and harmonic overtones.
     - **Chords**: Warm mid-register polyphonic triads (130–450 Hz) with soft attack and pad sustain.
     - **Melody**: Upper-register lead melody (400–900 Hz) with musical phrasing and subtle vibrato.
   - **Exact Sample-Accurate Duration**: Audio frames strictly equal `int(round(duration_s * sample_rate))`.
   - **Sample-Accurate Mix Reconstruction**: Mix is constructed directly from stem samples using documented gains:
     $$\text{mix}[t] = \text{clamp}\left(\text{round}\left(0.35 \cdot \text{bass}[t] + 0.30 \cdot \text{chords}[t] + 0.35 \cdot \text{melody}[t]\right), -32768, 32767\right)$$
     Reconstruction from exported stem files matches the exported mix sample-for-sample with 0 difference.

3. **Asynchronous In-Process Job Execution**:
   - `POST /api/v1/music/jobs` returns `HTTP 202 Accepted` with a unique `job_id` and tracking URL.
   - `GET /api/v1/jobs/{job_id}` returns lifecycle state (`queued`, `running`, `succeeded`, `failed`), progress indicator (0.0 to 1.0), and result URLs.
   - Real, accessible artifact endpoints: `/api/v1/jobs/{job_id}/artifacts/{filename}` serving actual `.wav` audio and `.json` manifests.

4. **Idempotency Support**:
   - Clients can include an `Idempotency-Key` header with `POST /api/v1/music/jobs`.
   - Repeating requests with the same key returns the existing job without duplicating synthesis work, attaching an `Idempotent-Replay: true` header.

5. **Music Manifest & Honest Rights/Licensing**:
   - Generates `music_manifest.json` for every completed job detailing request settings, seed, provider, stem filenames, gains, timings, warnings, and duration.
   - **Licensing Integrity**: Explicitly states `commercial_clearance: false` and `status: "unverified_mock_synthesis"`. Never falsely claims commercial clearance without verified legal proof.

6. **Preserved Health Checks**:
   - `GET /health` $\rightarrow$ `{"status": "ok"}`
   - `GET /ready` $\rightarrow$ `{"status": "ready"}`

---

## Project Structure

```
incubrix_audio/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entrypoint & lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py        # Aggregated v1 API router
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── music.py     # POST /api/v1/music/jobs
│   │           └── jobs.py      # GET /api/v1/jobs/{job_id} & artifacts
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings & environment variables
│   │   └── errors.py            # Consistent JSON exception handlers
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job.py               # Job state machine & domain model
│   │   └── schemas.py           # Pydantic request/response schemas
│   └── services/
│       ├── __init__.py
│       ├── audio_synthesis.py   # Multi-stem synthesizer & mix reconstruction
│       ├── job_runner.py        # Asynchronous job runner & scheduler
│       ├── job_store.py         # JobStore interface & InMemoryJobStore
│       ├── provider.py          # MusicProvider interface & MockMusicProvider
│       └── storage.py           # StorageService interface & LocalStorageService
├── tests/
│   ├── conftest.py              # Test fixtures & temporary storage setup
│   ├── test_audio_engine.py     # Duration, stems separation, & mix reconstruction tests
│   ├── test_health_and_ready.py # Health and readiness tests
│   ├── test_idempotency.py      # Idempotency header test cases
│   ├── test_job_lifecycle.py    # Submission, polling, & download tests
│   ├── test_manifest.py         # Manifest schema & licensing verification
│   └── test_validation.py       # Pydantic validation & error response tests
├── .env.example                 # Environment configuration template
├── .gitignore                   # Git ignore rules
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Project dependencies
└── README.md                    # Project documentation
```

---

## Setup & Running Locally

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Virtual environment (`venv`)

### 2. Configure Environment
Copy the example environment configuration:
```bash
cp .env.example .env
```
Default environment variables:
| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Deployment environment |
| `HOST` | `127.0.0.1` | Server host |
| `PORT` | `8000` | Server port |
| `PROVIDER_TYPE` | `mock` | Active synthesis engine |
| `STORAGE_DIR` | `storage` | Local directory for output artifacts |
| `DEFAULT_SAMPLE_RATE` | `44100` | Default audio sample rate (Hz) |
| `DEFAULT_TARGET_LUFS` | `-14.0` | Default loudness target (LUFS) |
| `DEFAULT_TEMPO_BPM` | `120` | Default musical tempo |
| `DEFAULT_KEY` | `C major` | Default musical key |
| `MIN_DURATION_S` | `5.0` | Minimum allowed audio duration (seconds) |
| `MAX_DURATION_S` | `300.0` | Maximum allowed audio duration (seconds) |

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the Application
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive API documentation will be available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Usage Examples

### 1. Health Checks
```bash
curl -X GET http://127.0.0.1:8000/health
# Response: {"status": "ok"}

curl -X GET http://127.0.0.1:8000/ready
# Response: {"status": "ready"}
```

### 2. Submit a Generation Job
```bash
curl -X POST http://127.0.0.1:8000/api/v1/music/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: client-req-001" \
  -d '{
    "prompt": "Relaxing lo-fi study background with mellow piano and upright bass",
    "duration_s": 15.0,
    "tempo_bpm": 85,
    "key": "C major",
    "loopable": true,
    "sections": [
      {"name": "intro", "start_s": 0.0, "end_s": 5.0},
      {"name": "main", "start_s": 5.0, "end_s": 15.0}
    ],
    "output": {
      "sample_rate": 44100,
      "target_lufs": -14.0,
      "formats": ["wav"]
    }
  }'
```
**Response (`HTTP 202 Accepted`):**
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "queued",
  "created_at": "2026-10-20T12:00:00Z",
  "message": "Job accepted and queued for processing",
  "job_url": "/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

### 3. Check Job Status & Retrieve Artifacts
```bash
curl -X GET http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d
```
**Response (`HTTP 200 OK` when succeeded):**
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "succeeded",
  "progress": 1.0,
  "created_at": "2026-10-20T12:00:00Z",
  "started_at": "2026-10-20T12:00:00.050Z",
  "completed_at": "2026-10-20T12:00:01.200Z",
  "error": null,
  "result": {
    "audio_url": "/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/mix.wav",
    "stems": {
      "bass": "/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/stem_bass.wav",
      "chords": "/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/stem_chords.wav",
      "melody": "/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/stem_melody.wav"
    },
    "manifest_url": "/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/music_manifest.json",
    "duration_s": 15.0,
    "sample_rate": 44100,
    "channels": 1,
    "format": "wav",
    "stem_gains": {
      "bass": 0.35,
      "chords": 0.30,
      "melody": 0.35
    }
  }
}
```

### 4. Downloading Stems & Mix
```bash
# Download Full Mix
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/mix.wav

# Download Bass Stem
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/stem_bass.wav

# Download Manifest
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/music_manifest.json
```

---

## Testing

The test suite runs with pytest and requires no API keys or external services:
```bash
pytest -v
```

### Test Coverage Summary:
- **`tests/test_validation.py`**: Validates missing/empty prompt, min/max duration bounds, tempo limits, section timestamps, overlapping sections, unsupported formats, and consistent JSON error formats.
- **`tests/test_health_and_ready.py`**: Verifies `/health` and `/ready` status codes and responses.
- **`tests/test_job_lifecycle.py`**: Verifies job submission (HTTP 202), async state transitions, progress updates, completion, 404 handling, and artifact downloads.
- **`tests/test_idempotency.py`**: Tests duplicate submissions with the same `Idempotency-Key` and ensures existing jobs are replayed without redundant synthesis.
- **`tests/test_audio_engine.py`**: Tests sample-accurate duration across various lengths, verifies 3 genuinely distinct non-silent stems, tests frequency separation, and verifies exact mathematical mix reconstruction ($max\_diff = 0$).
- **`tests/test_manifest.py`**: Validates `music_manifest.json` schema, settings, gains, timings, and unverified rights/licensing disclaimer.

---

## Production Transition Roadmap

To transition this Phase 1 foundation into an enterprise-ready production engine:

1. **Persistent Job Store**:
   - Replace `InMemoryJobStore` with a PostgreSQL implementation using SQLAlchemy or SQLModel for reliable persistence.
2. **Distributed Queue & Worker Process**:
   - Decouple API server from job execution using Redis and Celery / ARQ / Temporal to handle high concurrent synthesis loads.
3. **Cloud Object Storage**:
   - Replace `LocalStorageService` with an S3-compatible service (`boto3`) backed by AWS S3 or self-hosted MinIO with pre-signed download URLs.
4. **Generative Neural Audio Provider**:
   - Implement a new `MusicProvider` subclass (e.g. `AudiocraftProvider` or `MusicGenProvider`) connecting to GPU worker pools.
5. **Dynamic Audio Post-Processing**:
   - Integrate FFmpeg or Pyloudnorm for exact EBU R128 LUFS normalization and MP3/FLAC encoding.
