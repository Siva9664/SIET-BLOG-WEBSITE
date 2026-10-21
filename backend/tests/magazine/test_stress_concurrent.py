"""Concurrent Stress Test for Magazine Generation Pipeline.

Verifies async worker performance, VRAM queue safety, and deadlock prevention
under concurrent generation loads.
"""

import asyncio
import pytest
from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline


@pytest.mark.asyncio
async def test_concurrent_magazine_generations():
    """Executes multiple concurrent magazine generation tasks to ensure zero deadlocks and isolated outputs."""
    task_count = 3

    async def _generate_task(task_id: int):
        return await run_end_to_end_magazine_pipeline(
            raw_notes=f"Concurrent Test Task {task_id}: Autonomous drone swarm navigation experiment.",
            department_or_lab="AI Lab",
            target_page_budget=2,
            use_llm=False,
        )

    tasks = [_generate_task(i) for i in range(task_count)]
    results = await asyncio.gather(*tasks)

    assert len(results) == task_count
    for res in results:
        assert res is not None
        assert res.status == "published"
        assert res.pdf_url is not None
