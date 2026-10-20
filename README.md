# IncuBrix AI Background Music Engine

The **IncuBrix AI Background Music Engine** is a modular, asynchronous FastAPI service designed for generating high-quality background music with separated instrument stems, deterministic testing modes, real AI provider integration, automated manifest creation, and honest licensing verification.

---

> [!WARNING]
> **ARCHITECTURAL NOTICE — PHASE 1 & 2 DEV BASELINE**
> For this milestone, background jobs execute asynchronously in-process, and state is maintained in an **in-memory store** (`InMemoryJobStore`).
> **In-memory jobs do NOT survive server restarts or process crashes**, and cannot be shared across multiple horizontal worker processes.
> This setup is intended for local development, interface validation, and testing. Production deployment requires replacing these components with PostgreSQL, Redis/Celery, and MinIO/S3 (see [Production Transition Roadmap](#production-transition-roadmap)).

---

## Capabilities & Architecture

### Phase 1: Robust Foundation & Deterministic Mock Engine
- **Pydantic Validation**: Strict schema validation on `POST /api/v1/music/jobs` covering duration (5–300s), prompt, tempo (30–300 BPM), musical key, loopable flag, narration URL, and sequential section timestamps.
- **Consistent JSON Errors**: Predictable error payloads across all 422, 404, 400, and 500 responses:
  `{"error": {"code": "...", "message": "...", "details": [...]}}`.
- **Deterministic Oscillator Synthesizer**: Generates 3 genuinely separate synthesized stems (`bass`, `chords`, `melody`) with zero external API dependencies.
- **Sample-Accurate Duration & Mix Reconstruction**: Frames match duration down to the sample, and exported stems reconstruct the mix with 0 difference.
- **Idempotency**: Clients can include an `Idempotency-Key` header to safely retry requests without duplicating work.
- **Preserved Endpoints**: Preserves root `/health` (`{"status": "ok"}`) and `/ready` (`{"status": "ready"}`).

### Phase 2: Real AI Music Generation & Stem Separation
- **Soundverse Enterprise API Adapter**: Configurable real AI music provider implementing the [`MusicProvider`](file:///c:/Users/ELCOT/Desktop/incubrix_audio/app/services/provider.py) interface.
- **Instrumental Constraint**: Automatically augments prompts with tempo, key, section markers, and an explicit **"instrumental background music only, strictly no vocals, no singing, no spoken words"** instruction.
- **Demucs Stem Separation**: Integrates 6-stem (`drums`, `bass`, `guitar`, `piano`, `other`, `vocals`), 12-stem, or 2-stem separation.
- **Archive & Asset Inspection**: Dynamically inspects returned ZIP archives or role-tagged assets to identify and extract stems.
- **48 kHz WAV Normalization**: Decodes MP3/WAV/FLAC formats via `miniaudio` (with optional FFmpeg integration), resamples to 48 kHz, downmixes to mono, and adjusts to exact sample count.
- **Honest Stem Reconstruction Analysis**: Measures and logs actual Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Peak Error, and Signal-to-Error Ratio (SER in dB) between the provider's mix and the sum of stems. Does not fabricate perfect reconstruction for neural models.
- **Transparent Licensing & Cost**: Explicitly marks `commercial_clearance: false` and `unverified` in `music_manifest.json` until verified. Records billed costs ($0.07 music gen + $0.10 stem separation = $0.17 Royalty-Free).

---

## Project Structure

```
incubrix_audio/
├── app/
│   ├── main.py                  # FastAPI application entrypoint & lifespan
│   ├── api/
│   │   └── v1/
│   │       ├── router.py        # Aggregated v1 API router
│   │       └── endpoints/
│   │           ├── music.py     # POST /api/v1/music/jobs
│   │           └── jobs.py      # GET /api/v1/jobs/{job_id}, artifacts, & ZIP download
│   ├── core/
│   │   ├── config.py            # Pydantic Settings & environment variables
│   │   └── errors.py            # Consistent JSON exception handlers
│   ├── models/
│   │   ├── job.py               # Job state machine & domain model
│   │   └── schemas.py           # Pydantic request/response schemas
│   └── services/
│       ├── audio_normalizer.py  # 48kHz WAV normalization & reconstruction error metrics
│       ├── audio_synthesis.py   # Deterministic multi-stem oscillator synthesizer
│       ├── job_runner.py        # Asynchronous job execution coordinator
│       ├── job_store.py         # JobStore interface & InMemoryJobStore
│       ├── provider.py          # MusicProvider interface & MockMusicProvider
│       ├── soundverse_adapter.py# Soundverse Enterprise API client & provider
│       └── storage.py           # StorageService interface & LocalStorageService
├── tests/
│   ├── conftest.py              # Test fixtures & temporary storage isolation
│   ├── test_audio_engine.py     # Exact duration, stems separation, & mix tests
│   ├── test_health_and_ready.py # Health and readiness tests
│   ├── test_idempotency.py      # Idempotency header test cases
│   ├── test_job_lifecycle.py    # Submission, polling, & download tests
│   ├── test_manifest.py         # Manifest schema & licensing verification
│   ├── test_soundverse_adapter.py # Soundverse adapter, archive, retry, & error tests
│   ├── test_validation.py       # Pydantic validation & error response tests
│   └── test_zip_download.py     # ZIP packaging, stems inspection, & error handling tests
├── .env.example                 # Environment configuration template
├── .gitignore                   # Git ignore rules
├── AI_USE.md                    # AI usage and governance documentation
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Project dependencies
├── SOURCES.md                   # Soundverse API documentation references & pricing
└── README.md                    # Project documentation
```

---

## Setup & Running Locally

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Virtual environment (`venv`)

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Key environment configuration variables:
| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Deployment environment |
| `PROVIDER_TYPE` | `mock` | Active provider: `mock` (free local) or `soundverse` (real AI) |
| `STORAGE_DIR` | `storage` | Local directory for output artifacts |
| `SOUNDVERSE_API_KEY` | `""` | Enterprise API key (`sksoundverse_...`) |
| `SOUNDVERSE_BASE_URL` | `https://apiv2.soundverse.ai` | Soundverse Gateway Base URL |
| `SOUNDVERSE_MODEL_VERSION` | `v7` | Generation model version (`v7`, `v6`, `v5`) |
| `SOUNDVERSE_STEM_VARIANT` | `six-stem` | Stem model (`six-stem`, `12stem`, `2stem`) |
| `SOUNDVERSE_LICENSE_TIER` | `1` | License tier (1 = Royalty-Free) |

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the Application
Local Python:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. One-Command Docker Compose Quickstart
Start the full stack (API + MinIO S3 object storage):
```bash
docker compose up -d
```
Run containerized tests with one command:
```bash
docker compose run --rm test
```

### 6. OpenAPI 3.1 Specification
- Static OpenAPI 3.1 spec: [`openapi.yaml`](openapi.yaml)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## API Usage Examples

### 1. Submit a Generation Job
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
      "sample_rate": 48000,
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

### 2. Check Job Status & Retrieve Artifacts
```bash
curl -X GET http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d
```

### 3. Download Artifacts
```bash
# Mix WAV (48 kHz, exact duration)
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/mix.wav

# Separated Stems
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/stem_bass.wav
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/stem_drums.wav

# Manifest JSON
curl -O http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/artifacts/music_manifest.json
```

### 4. Download Complete Package as ZIP
Downloads a complete ZIP bundle containing the mix, stems, and manifest:
```bash
curl -O -J http://127.0.0.1:8000/api/v1/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/download
```

**ZIP Archive Contents (`incubrix_audio_{job_id}.zip`):**
```
incubrix_audio_{job_id}.zip
├── mix.wav                  # Master mix normalized to requested duration & sample rate
├── mix.mp3                  # Master mix MP3 (if exported/present)
├── music_manifest.json      # Complete generation manifest, timings, & licensing
└── stems/                   # Separated instrument stems (>= 3 parts)
    ├── stem_bass.wav
    ├── stem_chords.wav
    └── stem_melody.wav
```

**Response Codes:**
- `200 OK`: Returns binary `application/zip` with `Content-Disposition: attachment; filename="incubrix_audio_{job_id}.zip"`.
- `409 Conflict`: If the job is still queued or running (`JOB_NOT_READY`), or failed (`JOB_FAILED`).
- `404 Not Found`: If the job does not exist or artifacts are missing.

### 5. Upload Audio File (Narration / Reference Input)
Uploads an audio file (.wav, .mp3, .flac) to storage for use as a `narration_url`:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/audio/upload \
  -F "file=@voiceover.wav;type=audio/wav"
```

### 6. Execute Batch Test Scenarios
Runs the batch runner against test scenarios defined in `scripts/batch_inputs.json`, polling all jobs and downloading mix audio, stems, manifests, and ZIP packages:
```bash
python scripts/batch_runner.py --api-url http://127.0.0.1:8000 --output-dir batch_output
```
Outputs and full audit report are saved to `batch_output/batch_summary.json`.

---

## Manual Steps for Live Soundverse Generation

To verify live generation with the Soundverse Enterprise API:

1. **Obtain API Key**:
   - Register at [https://platform.soundverse.ai](https://platform.soundverse.ai).
   - Generate an enterprise API key at [https://platform.soundverse.ai/enterprise-platform/apikeys](https://platform.soundverse.ai/enterprise-platform/apikeys).
   - Verify token balance at `GET /v1/account/balance`.
2. **Update Environment (`.env`)**:
   ```env
   PROVIDER_TYPE=soundverse
   SOUNDVERSE_API_KEY=sksoundverse_your_live_key_here
   SOUNDVERSE_MODEL_VERSION=v7
   SOUNDVERSE_STEM_VARIANT=six-stem
   SOUNDVERSE_LICENSE_TIER=1
   ```
3. **Start Server**:
   ```bash
   uvicorn app.main:app --reload
   ```
4. **Submit Live Request**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/music/jobs \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: live-test-001" \
     -d '{"prompt": "Cinematic ambient pads with gentle percussion", "duration_s": 15.0}'
   ```
5. **Poll and Verify**:
   - Poll `GET /api/v1/jobs/{job_id}` until `status == "succeeded"`.
   - Download `music_manifest.json` and verify `stem_reconstruction_validation` (MAE, RMSE, Signal-to-Error ratio).
   - Listen to `mix.wav` and individual stems (`stem_drums.wav`, `stem_bass.wav`, `stem_piano.wav`, etc.).

---

## Testing

Run the full pytest suite (48 automated tests, zero API keys required, zero paid costs):
```bash
pytest -v
```

### Test Suite Overview:
- **`tests/test_audit_standards.py`** (5 tests):
  - OpenAPI 3.1 schema completeness and routing matches.
  - Correlation ID middleware (`X-Correlation-ID` extraction & generation).
  - Structured JSON logging formatter.
  - Audio file upload endpoint (`POST /api/v1/audio/upload`) and 422 validation.
  - S3StorageService interface & local caching.
- **`tests/test_batch_runner.py`** (1 test): Full automated multi-scenario batch execution, progress polling, artifact download, and summary reporting.
- **`tests/test_zip_download.py`** (7 tests): ZIP packaging, directory structure (`stems/`), `mix.mp3` inclusion, 409 queued/running errors, 409 failed errors, 404 nonexistent jobs, and missing artifacts.
- **`tests/test_soundverse_adapter.py`** (10 tests):
  - Instrumental prompt construction & explicit no-vocals rule.
  - Missing API key validation.
  - End-to-end mocked music generation and 6-stem separation.
  - Stem separation ZIP archive extraction & role parsing.
  - Rate limiting (429 RateLimited) with exponential backoff and retry.
  - Non-retryable provider errors (400, 402, 422).
  - Polling timeout handling.
  - Corrupted audio detection.
  - Honest stem reconstruction error calculation.
  - Configurable provider selection via `PROVIDER_TYPE`.
- **`tests/test_audio_engine.py`** (6 tests): Sample-accurate duration, 3 distinct stems, frequency separation, mix reconstruction.
- **`tests/test_job_lifecycle.py`** (3 tests): Job creation, polling, artifact retrieval, 404 handling.
- **`tests/test_idempotency.py`** (2 tests): `Idempotency-Key` header replaying and dedup.
- **`tests/test_manifest.py`** (1 test): Manifest schema, settings, timings, unverified licensing.
- **`tests/test_validation.py`** (11 tests): Bounds, missing fields, overlapping sections, consistent error payloads.
- **`tests/test_health_and_ready.py`** (2 tests): `/health` and `/ready` endpoints.

---

## Production Transition Roadmap

1. **Persistent Job Store**: Replace `InMemoryJobStore` with PostgreSQL (SQLAlchemy/SQLModel) to survive restarts.
2. **Distributed Queue**: Offload generation and stem separation to Redis/Celery or Temporal.
3. **Cloud Object Storage**: Replace `LocalStorageService` with AWS S3 or MinIO, generating pre-signed expiring download URLs.
4. **Billing & Token Reservation**: Add pre-flight balance checks against `GET /v1/account/balance` before queuing jobs.
