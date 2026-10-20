#!/usr/bin/env python3
"""Batch Runner for IncuBrix Audio Engine.

Executes a sequence of music generation scenarios against the API,
tracks progress, downloads outputs (mix, stems, manifest, ZIP archive),
and compiles a batch execution summary report.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx


async def run_batch(
    api_url: str = "http://127.0.0.1:8000",
    inputs_path: Path = Path("scripts/batch_inputs.json"),
    output_dir: Path = Path("batch_output"),
    timeout_s: float = 120.0,
    poll_interval_s: float = 0.5,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Executes a batch of test inputs, saves artifacts, and returns batch report."""
    if not inputs_path.exists():
        raise FileNotFoundError(f"Batch inputs file not found: {inputs_path}")

    with open(inputs_path, "r", encoding="utf-8") as f:
        scenarios: List[Dict[str, Any]] = json.load(f)

    output_dir.mkdir(parents=True, exist_ok=True)
    batch_t0 = time.time()
    results: List[Dict[str, Any]] = []

    print(f"\n=======================================================")
    print(f" IncuBrix Audio Engine — Batch Execution Runner")
    print(f" Target API: {api_url}")
    print(f" Total Scenarios: {len(scenarios)}")
    print(f" Output Directory: {output_dir.resolve()}")
    print(f"=======================================================\n")

    # Use provided client or initialize an AsyncClient
    close_client = False
    if client is None:
        client = httpx.AsyncClient(base_url=api_url, timeout=30.0)
        close_client = True

    try:
        for idx, scenario in enumerate(scenarios, start=1):
            scenario_id = scenario.get("id", f"scenario_{idx}")
            prompt = scenario.get("prompt", "")
            duration = scenario.get("duration_s", 5.0)

            print(f"[{idx}/{len(scenarios)}] Dispatching '{scenario_id}': \"{prompt[:45]}...\" ({duration}s)")
            t_start = time.time()

            job_dir = output_dir / scenario_id
            job_dir.mkdir(parents=True, exist_ok=True)

            # 1. Dispatch job to API
            idempotency_key = f"batch-run-{scenario_id}"
            headers = {"Idempotency-Key": idempotency_key}

            try:
                post_resp = await client.post("/api/v1/music/jobs", json=scenario, headers=headers)
            except Exception as exc:
                print(f"    [ERROR] Failed to connect to API: {exc}")
                results.append({
                    "id": scenario_id,
                    "status": "failed",
                    "error": f"Connection error: {exc}",
                    "elapsed_s": round(time.time() - t_start, 2),
                })
                continue

            if post_resp.status_code not in (200, 202):
                print(f"    [ERROR] Job rejected: HTTP {post_resp.status_code} - {post_resp.text}")
                results.append({
                    "id": scenario_id,
                    "status": "failed",
                    "error": f"HTTP {post_resp.status_code}: {post_resp.text}",
                    "elapsed_s": round(time.time() - t_start, 2),
                })
                continue

            job_data = post_resp.json()
            job_id = job_data["job_id"]
            correlation_id = post_resp.headers.get("X-Correlation-ID")
            print(f"    -> Job created: {job_id} (Correlation: {correlation_id})")

            # 2. Poll for completion
            poll_deadline = time.time() + timeout_s
            job_status = "queued"
            final_job_info = None

            while time.time() < poll_deadline:
                poll_resp = await client.get(f"/api/v1/jobs/{job_id}")
                if poll_resp.status_code == 200:
                    final_job_info = poll_resp.json()
                    job_status = final_job_info.get("status", "unknown")
                    progress = final_job_info.get("progress", 0.0)

                    if job_status in ("succeeded", "failed"):
                        break
                    print(f"       Status: {job_status} ({int(progress * 100)}%)...", end="\r")

                await asyncio.sleep(poll_interval_s)

            elapsed = round(time.time() - t_start, 2)

            if job_status != "succeeded":
                error_msg = (final_job_info or {}).get("error") or "Job timed out"
                print(f"\n    [FAILED] {scenario_id} ({job_status}): {error_msg}")
                results.append({
                    "id": scenario_id,
                    "job_id": job_id,
                    "status": job_status,
                    "error": error_msg,
                    "elapsed_s": elapsed,
                })
                continue

            print(f"\n    [SUCCESS] Completed in {elapsed}s. Downloading outputs...")

            # 3. Download mix audio
            downloaded_files = []
            res_meta = final_job_info.get("result", {})

            mix_url = res_meta.get("audio_url")
            if mix_url:
                mix_resp = await client.get(mix_url)
                if mix_resp.status_code == 200:
                    mix_path = job_dir / "mix.wav"
                    mix_path.write_bytes(mix_resp.content)
                    downloaded_files.append("mix.wav")

            # 4. Download stems
            stems_dict = res_meta.get("stems", {})
            stems_dir = job_dir / "stems"
            stems_dir.mkdir(parents=True, exist_ok=True)

            for stem_name, stem_url in stems_dict.items():
                stem_resp = await client.get(stem_url)
                if stem_resp.status_code == 200:
                    stem_filename = stem_url.split("/")[-1]
                    (stems_dir / stem_filename).write_bytes(stem_resp.content)
                    downloaded_files.append(f"stems/{stem_filename}")

            # 5. Download manifest
            manifest_url = res_meta.get("manifest_url")
            if manifest_url:
                manifest_resp = await client.get(manifest_url)
                if manifest_resp.status_code == 200:
                    (job_dir / "music_manifest.json").write_bytes(manifest_resp.content)
                    downloaded_files.append("music_manifest.json")

            # 6. Download complete ZIP archive
            zip_resp = await client.get(f"/api/v1/jobs/{job_id}/download")
            if zip_resp.status_code == 200:
                zip_path = job_dir / f"incubrix_audio_{job_id}.zip"
                zip_path.write_bytes(zip_resp.content)
                downloaded_files.append(zip_path.name)

            results.append({
                "id": scenario_id,
                "job_id": job_id,
                "status": "succeeded",
                "duration_s": duration,
                "elapsed_s": elapsed,
                "sample_rate": res_meta.get("sample_rate"),
                "stems_count": len(stems_dict),
                "artifacts_saved": downloaded_files,
                "output_dir": str(job_dir),
            })

    finally:
        if close_client:
            await client.aclose()

    total_batch_time = round(time.time() - batch_t0, 2)
    succeeded_count = sum(1 for r in results if r.get("status") == "succeeded")
    failed_count = sum(1 for r in results if r.get("status") != "succeeded")

    batch_summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_scenarios": len(scenarios),
        "succeeded": succeeded_count,
        "failed": failed_count,
        "total_elapsed_s": total_batch_time,
        "results": results,
    }

    # Save summary report
    summary_path = output_dir / "batch_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, indent=2)

    # Print summary table
    print(f"\n=======================================================")
    print(f" Batch Execution Completed in {total_batch_time}s")
    print(f" Summary: {succeeded_count}/{len(scenarios)} succeeded, {failed_count} failed")
    print(f" Report saved: {summary_path.resolve()}")
    print(f"=======================================================\n")
    print(f"{'ID':<15} | {'STATUS':<10} | {'DURATION':<9} | {'TIME(s)':<8} | {'STEMS':<6} | {'OUTPUT DIR'}")
    print("-" * 80)
    for r in results:
        dur = f"{r.get('duration_s', '-')}s"
        stems = r.get("stems_count", "-")
        out = Path(r.get("output_dir", "-")).name
        print(f"{r.get('id', '-'):<15} | {r.get('status', '-'):<10} | {dur:<9} | {r.get('elapsed_s', '-'):<8} | {stems:<6} | {out}")
    print("\n")

    return batch_summary


def main():
    parser = argparse.ArgumentParser(description="IncuBrix Audio Engine Batch Runner")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://127.0.0.1:8000"), help="Base URL of IncuBrix Audio API")
    parser.add_argument("--inputs", default="scripts/batch_inputs.json", help="Path to JSON file containing test scenarios")
    parser.add_argument("--output-dir", default="batch_output", help="Directory where outputs and report are saved")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-job completion timeout in seconds")

    args = parser.parse_args()

    summary = asyncio.run(
        run_batch(
            api_url=args.api_url,
            inputs_path=Path(args.inputs),
            output_dir=Path(args.output_dir),
            timeout_s=args.timeout,
        )
    )

    if summary["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
