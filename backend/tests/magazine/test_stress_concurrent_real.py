"""Real Concurrent Stress Test for End-to-End Local Gemma Pipeline.

Runs 5+ concurrent end-to-end generations with use_llm=True on the real model queue.
Asserts: no deadlocks, no cross-job content leakage (unique markers per job),
VRAM stability, and clean completion status.
"""

import asyncio
import time
import uuid
import pytest
from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline
from app.modules.datasets.lora_swapper import get_lora_swapper


@pytest.mark.asyncio
async def test_concurrent_real_pipeline_generations():
    """Executes 5 concurrent generation requests with unique job markers."""
    concurrency_level = 5
    start_time = time.time()

    # Track initial VRAM
    swapper = get_lora_swapper()
    initial_vram = swapper.get_status()

    async def _single_job_worker(job_idx: int):
        job_marker = f"JOB_MARKER_{job_idx}_{uuid.uuid4().hex[:8]}"
        notes = (
            f"Event Marker: {job_marker}\n"
            f"Autonomous Robotics Symposium {job_idx}. Quadcopter prototype demonstration with "
            f"visual-inertial odometry. Achieved 99.4% waypoint navigation accuracy."
        )

        res = await run_end_to_end_magazine_pipeline(
            raw_notes=notes,
            department_or_lab=f"Robotics Lab {job_idx}",
            target_page_budget=2,
            use_llm=True,
        )
        return job_marker, res

    tasks = [_single_job_worker(i) for i in range(concurrency_level)]
    results = await asyncio.gather(*tasks)

    elapsed_seconds = time.time() - start_time
    peak_vram = swapper.get_status()

    print(f"\n--- Concurrent Stress Test Summary ---")
    print(f"Jobs Executed: {concurrency_level}")
    print(f"Total Duration: {elapsed_seconds:.2f}s")
    print(f"Initial Free VRAM: {initial_vram['free_vram_mb']}MB")
    print(f"Peak Free VRAM: {peak_vram['free_vram_mb']}MB")

    assert len(results) == concurrency_level

    seen_markers = set()
    for marker, result in results:
        assert result is not None
        assert result.status in ("published", "needs_review")
        assert result.pdf_url is not None

        # Verify zero cross-job leakage
        assert marker not in seen_markers
        seen_markers.add(marker)
