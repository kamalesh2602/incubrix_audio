# Evidence Index — IncuBrix Audio Engine Submission

This index maps every claim and requirement in `REPORT.md` to its verifiable evidence file in `submission/`.

| Claim / Standard | Verification Evidence File | Status |
|---|---|---|
| **1. One-command Docker Startup & Tests** | `Dockerfile`, `docker-compose.yml`, `submission/test_pack/test_results.xml` | **Verified** |
| **2. OpenAPI 3.1 Specification** | `openapi.yaml`, `submission/test_pack/test_results.xml` (test_openapi_specification) | **Verified** |
| **3. Asynchronous Job Status & Progress** | `submission/audio_pack/TEST-01-MOCK-AMBIENT-5S/job_status.json` | **Verified** |
| **4. Idempotency Replay Header** | `submission/test_pack/hardcase_08_idempotency_replay.json` | **Verified** |
| **5. Structured JSON Error Envelope** | `submission/test_pack/hardcase_01_missing_prompt.json` through `hardcase_11_nonexistent_job_404.json` | **Verified** |
| **6. Environment Configuration** | `app/core/config.py`, `.env.example`, `submission/test_pack/test_results.xml` | **Verified** |
| **7. Audio File Upload Endpoint** | `submission/test_pack/test_results.xml` (test_audio_file_upload_success_and_validation) | **Verified** |
| **8. S3-Compatible Storage (MinIO)** | `app/services/storage.py`, `submission/test_pack/test_results.xml` (test_s3_storage_service_interface) | **Verified** |
| **9. Structured JSON Logs & Correlation IDs** | `submission/audio_pack/TEST-01-MOCK-AMBIENT-5S/logs.txt`, `app/core/logging.py` | **Verified** |
| **10. Complete Manifests** | `submission/audio_pack/TEST-01-MOCK-AMBIENT-5S/music_manifest.json` | **Verified** |
| **11. Batch Execution Runner** | `scripts/batch_runner.py`, `submission/test_pack/test_results.xml` (test_batch_runner_execution) | **Verified** |
| **12. Soundverse Adapter Protocol** | `app/services/soundverse_adapter.py`, `submission/test_pack/test_results.xml` (10 tests) | **Verified (Mocked Protocol)** |
| **13. Soundverse Live Generation** | `submission/audio_pack/TEST-05-SOUNDVERSE-LIVE-UNCONFIGURED/NOTE.md` | **Unverified (No live API key)** |
| **14. ZIP Archive Packaging** | `submission/audio_pack/TEST-01-MOCK-AMBIENT-5S/`, `app/api/v1/endpoints/jobs.py` | **Verified** |
