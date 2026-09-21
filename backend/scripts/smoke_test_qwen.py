"""Live smoke test script for local Qwen3 14B on Ollama using a synthetic college event report."""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.infrastructure.ai.constants import DEFAULT_STRICT_GROUNDING_INSTRUCTION
from app.infrastructure.ai.ollama_provider import OllamaProvider
from app.infrastructure.ai.schemas import MagazineEditorialContent

SYNTHETIC_EVENT_REPORT = """
EVENT REPORT (SYNTHETIC BENCHMARK DATA)
Event: SIET Autonomous Systems Symposium 2026
Organized by: Department of Artificial Intelligence & Robotics, Sri Shakthi Institute of Engineering & Technology
Date: February 26, 2026
Venue: Dr. Radhakrishnan Auditorium, Campus Block C
Keynote Speaker: Dr. Arvind Ramanathan, Lead Systems Architect at Autonomous Motion Labs
Attendees: 310 registered undergraduate engineering students and 24 faculty members
Event Highlights:
- Morning Keynote on Edge-Optimized Reinforcement Learning for Quadruped Locomotion.
- Project Exhibition: 18 student prototypes demonstrated.
- Top Honors:
  * 1st Place (Gold Medal & Cash Award Rs. 50,000): Team RoverTech (Students: Aarav Patel, Deepa Nair) for low-latency visual-inertial odometry on custom FPGA.
  * 2nd Place (Silver Medal & Cash Award Rs. 25,000): Team AeroNav (Students: Karthik V., Sneha Roy) for GPS-denied indoor drone navigation.
Uploaded Photos: 3
Photo 1: Dr. Arvind Ramanathan delivering keynote address on edge RL.
Photo 2: Team RoverTech demonstrating FPGA odometry prototype to evaluation panel.
Photo 3: Group photograph with winners, Principal, and faculty mentors.
"""


async def run_smoke_test():
    print("=" * 70)
    print("SIET AI EDITORIAL INTELLIGENCE — LOCAL QWEN3 14B SMOKE TEST")
    print("=" * 70)

    provider = OllamaProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
    )

    print(f"\n[1] Checking Provider Health at {provider.base_url}...")
    start_time = time.perf_counter()
    health = await provider.health()
    health_latency = time.perf_counter() - start_time
    print(f"Health Response ({health_latency:.3f}s): {json.dumps(health, indent=2)}")

    if health.get("status") != "healthy":
        print(f"\n[FAILED] Ollama health check returned: {health.get('status')}")
        sys.exit(1)

    print(f"\n[2] Executing Structured Generation against '{provider.model}'...")
    print("Strict Grounding Instruction Injected:")
    print("-" * 50)
    print(DEFAULT_STRICT_GROUNDING_INSTRUCTION)
    print("-" * 50)

    prompt = f"""You are the editorial intelligence writer for SIET Magazine.
Generate a structured magazine issue based STRICTLY on the synthetic event report below.
Do NOT invent any external details, dates, companies, or people not listed in the report.

=== SYNTHETIC SOURCE REPORT ===
{SYNTHETIC_EVENT_REPORT}
"""

    gen_start = time.perf_counter()
    try:
        result: MagazineEditorialContent = await provider.generate_structured(
            prompt=prompt,
            schema=MagazineEditorialContent,
            system_instruction=DEFAULT_STRICT_GROUNDING_INSTRUCTION,
        )
        gen_duration = time.perf_counter() - gen_start
    except Exception as e:
        print(f"\n[FAILED] Structured generation error: {e}")
        sys.exit(1)

    print(f"\n[SUCCESS] Generation completed in {gen_duration:.2f}s")
    print("\n" + "=" * 70)
    print("GENERATED STRUCTURED EDITORIAL OUTPUT:")
    print("=" * 70)
    print(f"Issue Title : {result.magazine_issue_title}")
    print(f"Description : {result.description}")
    print(f"TOC Summary : {result.toc_summary}")
    print(f"Captions ({len(result.captions)} total):")
    for idx, c in enumerate(result.captions, 1):
        print(f"  {idx}. {c}")
    print("\nWriteup Body:")
    print(result.writeup)
    print("=" * 70)

    # Verification checks
    print("\n[3] Grounding and Schema Adherence Assertions:")
    assert len(result.magazine_issue_title.strip()) > 0, "Title must not be empty"
    assert len(result.description.strip()) > 0, "Description must not be empty"
    assert len(result.writeup.strip()) > 0, "Writeup must not be empty"
    assert len(result.toc_summary.strip()) > 0, "TOC Summary must not be empty"
    assert len(result.captions) >= 1, "Must generate at least 1 caption"

    # Factual grounding assertions based strictly on synthetic report
    writeup_and_desc = (result.writeup + " " + result.description + " " + result.magazine_issue_title).lower()
    assert (
        "rovertech" in writeup_and_desc
        or "autonomous" in writeup_and_desc
        or "siet" in writeup_and_desc
        or "symposium" in writeup_and_desc
    ), "Content should be grounded in the synthetic report themes"

    print("✓ All assertions PASSED successfully!")
    print("\nSmoke test passed cleanly!")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
