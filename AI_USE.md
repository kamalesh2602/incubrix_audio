# AI Usage & Implementation Governance

This document records the principles, scope, and safeguards applied when utilizing AI in the design, development, and testing of the **IncuBrix AI Background Music Engine** (Phase 1 and Phase 2).

---

## 1. Scope of AI Involvement

An advanced AI coding assistant (Google DeepMind Antigravity) was utilized to pair-program and implement:
1. **Architecture & API Design**:
   - Designing clean Pydantic request/response schemas for `/api/v1/music/jobs` with cross-field validators.
   - Crafting provider abstractions (`MusicProvider`) and storage abstractions (`JobStore`, `StorageService`).
2. **Provider Documentation Inspection**:
   - Live inspection and parsing of the official Soundverse Enterprise API documentation (`https://platform.soundverse.ai/docs`).
   - Extracting exact route signatures, status shapes, error codes, and Demucs stem-separation variants directly from source documents without guessing.
3. **Audio Engineering & DSP**:
   - Developing sample-rate converters (resampling to 48 kHz WAV) and sample-accurate duration trimmers/padders.
   - Implementing stem separation archive inspection (.zip extraction) and stem role parsing.
   - Implementing mathematical reconstruction discrepancy analysis (MAE, RMSE, Max Error, Signal-to-Error Ratio in dB).
4. **Automated Testing Suite**:
   - Writing comprehensive, mock-based pytest suites (35 unit and integration tests) providing complete test coverage without making paid outbound API calls.

---

## 2. Ethical Safeguards & Truthful Reporting

1. **No Fabricated Verification**:
   - Synthetic mock generation (Phase 1) is clearly distinguished from real AI provider integration (Phase 2).
   - In live AI generation with stem separation, reconstruction error is measured and reported honestly; neural stem separation artifacts are never hidden or claimed to be mathematically lossless.
2. **Strict Rights & Commercial Clearance Policy**:
   - Generated manifests explicitly designate `commercial_clearance: false` and note that commercial clearance has not been legally verified.
   - Falsely claiming commercial clearance without contractual proof is strictly prohibited.
3. **Cost Protection**:
   - The engine defaults to `PROVIDER_TYPE=mock` out-of-the-box.
   - Automated tests run against local mock transports and never trigger billed provider calls.
4. **Credential Security**:
   - Sensitive credentials (`SOUNDVERSE_API_KEY`) are protected using Pydantic's `SecretStr` to prevent exposure in logs, traces, or string conversions.
