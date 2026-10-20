import json
from pathlib import Path
import pytest
from httpx import AsyncClient

from scripts.batch_runner import run_batch


@pytest.mark.asyncio
async def test_batch_runner_execution(async_client: AsyncClient, tmp_path: Path):
    # 1. Create a minimal 2-scenario input file
    scenarios = [
        {
            "id": "test-batch-01",
            "prompt": "Soft acoustic folk guitar",
            "duration_s": 5.0,
            "tempo_bpm": 100,
            "key": "C major",
        },
        {
            "id": "test-batch-02",
            "prompt": "Ambient lo-fi synthesizer",
            "duration_s": 5.0,
            "tempo_bpm": 85,
            "key": "A minor",
        },
    ]
    input_file = tmp_path / "test_inputs.json"
    input_file.write_text(json.dumps(scenarios), encoding="utf-8")

    out_dir = tmp_path / "batch_out"

    # 2. Run batch runner with async_client
    summary = await run_batch(
        api_url="http://test",
        inputs_path=input_file,
        output_dir=out_dir,
        timeout_s=30.0,
        poll_interval_s=0.05,
        client=async_client,
    )

    # 3. Assertions on summary
    assert summary["total_scenarios"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0
    assert len(summary["results"]) == 2

    # 4. Assertions on saved artifacts
    for item in summary["results"]:
        job_id = item["job_id"]
        scenario_id = item["id"]
        job_folder = out_dir / scenario_id

        assert (job_folder / "mix.wav").exists()
        assert (job_folder / "music_manifest.json").exists()
        assert (job_folder / "stems").exists()
        assert (job_folder / f"incubrix_audio_{job_id}.zip").exists()

        manifest_data = json.loads((job_folder / "music_manifest.json").read_text(encoding="utf-8"))
        assert manifest_data["job_id"] == job_id

    # 5. Check batch_summary.json exists on disk
    assert (out_dir / "batch_summary.json").exists()
