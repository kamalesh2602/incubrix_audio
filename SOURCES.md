# Sources & Documentation Reference

This document records the official documentation, endpoints, payload formats, error schemas, pricing structures, and technical citations used for the Soundverse Enterprise API integration in Phase 2 of the IncuBrix Audio Engine.

---

## 1. Official Documentation Reference

- **Documentation Portal**: [https://platform.soundverse.ai/docs](https://platform.soundverse.ai/docs)
- **API Keys & Dashboard**: [https://platform.soundverse.ai/enterprise-platform/apikeys](https://platform.soundverse.ai/enterprise-platform/apikeys)
- **Tool Catalog**: [https://platform.soundverse.ai/docs/tool-catalog](https://platform.soundverse.ai/docs/tool-catalog)
- **Compat Routes**: [https://platform.soundverse.ai/docs/compat-routes](https://platform.soundverse.ai/docs/compat-routes)
- **Music Generation**: [https://platform.soundverse.ai/docs/music-generation](https://platform.soundverse.ai/docs/music-generation)
- **Stem Separation**: [https://platform.soundverse.ai/docs/stem-separation](https://platform.soundverse.ai/docs/stem-separation)
- **Active Gateway Base URL**: `https://apiv2.soundverse.ai`

---

## 2. Authentication & Idempotency

- **Authentication Header**:
  ```http
  Authorization: Bearer sksoundverse_<your_api_key>
  Content-Type: application/json
  ```
- **Idempotency-Key Header**:
  ```http
  Idempotency-Key: <unique_client_key_up_to_200_chars>
  ```
  Permitted characters: `[A-Za-z0-9_.:-]`. A repeated call with the same key returns the existing task without duplicate billing.

---

## 3. Endpoints & Operations

### A. Music Generation (Instrumental)
- **Compat Route**: `POST /v7/generate/music` (also available for `v6` and `v5`)
- **Request Body**:
  ```json
  {
    "prompt": "warm lo-fi hip-hop with vinyl crackle, instrumental background music only, strictly no vocals",
    "parameters": {
      "versions": 1
    }
  }
  ```
- **Response (`201 Created`)**:
  ```json
  {
    "job_id": "gen-task-uuid",
    "status": "queued"
  }
  ```
- **Native Route**: `POST /v1/generations` with `tool_id="generate_music_v7"` and `payload_json`.

### B. Stem Separation (Demucs Models)
- **Supported Variants**:
  - `six-stem` (`POST /v1/generate/stem-separation/six-stem`): 6-way Demucs split into `drums`, `bass`, `guitar`, `piano`, `other`, `vocals`.
  - `12stem` (`POST /v1/generate/stem-separation/all-stems`): 12-stem Demucs split.
  - `2stem` (`POST /v1/generate/stem-separation/instruments` or `/vocals`): Karaoke split producing `vocals` and `instrumental`.
- **Request Body**:
  ```json
  {
    "audioUrl": "https://storage.soundverse.ai/.../mix.wav"
  }
  ```
- **Response (`201 Created`)**:
  ```json
  {
    "job_id": "stem-task-uuid",
    "status": "queued"
  }
  ```

### C. Status Polling
- **Compat Route**: `GET /v7/status?job_id={job_id}`
- **Native Route**: `GET /v1/generations/{task_id}`
- **Response Format**:
  ```json
  {
    "job_id": "gen-task-uuid",
    "status": "completed",
    "error_message": "",
    "output": {
      "assets": [
        {
          "file_id": "file-asset-uuid",
          "role": "mix",
          "name": "mix.wav",
          "url": "https://storage.soundverse.ai/..."
        }
      ]
    }
  }
  ```
- **Statuses**: `queued`, `processing`, `completed`, `failed`.

### D. Asset Download
- **Endpoint**: `GET /v1/files/{file_id}/download`
- **Behavior**: Returns a short-lived signed URL scoped to the API key owner (or direct audio stream).
- **Security Rule**: Do not treat raw private storage locators (`output.assets[].url`) as public browser URLs; always query the download route.

---

## 4. Error Hierarchy & Retry Policies

Soundverse returns specific error class names in the `error` body field:

| HTTP Status | Error Class | Retryable | Description |
|---|---|---|---|
| 400 | `UnknownTool` | No | Tool ID or operation not found; fix request |
| 402 | `InsufficientFunds` | No | Token/credit reservation failed; top up account |
| 422 | `ToolNotPriced` | No | Tool has no platform pricing configured for license tier |
| 422 | `InvalidGenerationInput` | No | Request failed capability-specific validation |
| 429 | `RateLimited` | **Yes** | Per-tool rate limit exceeded; back off and retry |
| 503 | `DependencyUnavailable`| **Yes** | Internal processing dependency temporarily unavailable |
| 401 | `UNAUTHENTICATED` | No | Missing Bearer token |
| 401 | `INVALID_API_KEY` | No | Key invalid or revoked |
| 403 | `FORBIDDEN` | No | Task exists but belongs to another account |
| 404 | `NOT_FOUND` | No | Task ID does not exist |

---

## 5. Pricing & License Matrix

### Music Generation (per track)
| Version | Royalty-Free (Tier 1) | Standard (Tier 2) | Distribution (Tier 3) | Sync (Tier 4) | Master (Tier 5) |
|---|---|---|---|---|---|
| v5 / v6 / v7 | **$0.07** | $0.11 | $0.14 | $0.28 | $0.70 |

### Stem Separation (per separation)
| Model Variant | Royalty-Free | Standard | Distribution | Sync | Master |
|---|---|---|---|---|---|
| 6-stem (v5) | **$0.10** | $0.10 | $0.10 | $0.10 | $0.10 |
| 12stem | $0.10 | $0.10 | $0.10 | $0.10 | $0.10 |
| 2stem | $0.10 | $0.10 | $0.10 | $0.10 | $0.10 |

**Total Estimated Cost for Music Generation + 6-Stem Separation (Royalty-Free)**: **$0.17 USD**.

---

## 6. Rights & Licensing Policy

- Output tracks generated under Tier 1 (`LICENSE_ROYALTY_FREE`) are designated as royalty-free under Soundverse terms.
- **Verification Rule**: Commercial clearance is marked as `commercial_clearance: false` in manifests until enterprise licensing contracts and account terms are legally verified. Never claim commercial clearance without verification.

---

## 7. External Libraries & Core Specifications

- **FastAPI** (`v0.115+`): High-performance ASGI web framework with native OpenAPI 3.1.0 generation.
- **Pydantic & Pydantic-Settings** (`v2.x`): Data validation and typed environment configuration.
- **miniaudio** (`v1.71+`): Portable, multi-format audio decoding (WAV, MP3, FLAC) and resampling.
- **boto3** (`v1.34+`): AWS S3 / MinIO compatible cloud object storage client.
- **HTTPX** (`v0.28+`): Next-generation HTTP client supporting async transports and test execution.
- **PyYAML** (`v6.0+`): YAML parsing and serialization for OpenAPI 3.1 specifications.
- **OpenAPI 3.1.0 Specification**: Industry-standard RESTful API description standard.
