import asyncio
import time
import httpx
from app.core.security import create_access_token

BASE_URL = "http://localhost:8020/api/v1"
ADMIN_TOKEN = create_access_token("1", "admin")
HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json",
}

TEST_PAYLOAD = {
    "event_name": "SIET International AI & Robotics Symposium 2026",
    "event_date": "2026-08-31",
    "raw_notes": (
        "Sri Shakthi Institute of Engineering and Technology hosted the international AI & Robotics Symposium. "
        "Over 45 research teams demonstrated autonomous quadcopters, mechatronic limbs, and quantum edge computing models. "
        "Keynote address was delivered by Dr. K. Ramanathan on high-precision neural architecture search."
    ),
    "photo_count": 4,
}

async def send_request(client: httpx.AsyncClient, req_id: int) -> dict:
    start_time = time.time()
    try:
        # Alternating between ai/auto-generate and RAG auto-generate
        endpoint = "/admin/magazine/auto-generate" if req_id % 2 == 0 else "/admin/magazine/ai/auto-generate"
        payload = {"document_ids": [1, 2], "event_name": f"SIET Event #{req_id}"} if req_id % 2 == 0 else TEST_PAYLOAD
        
        res = await client.post(
            f"{BASE_URL}{endpoint}",
            json=payload,
            headers=HEADERS,
            timeout=30.0,
        )
        duration = round(time.time() - start_time, 3)
        return {
            "req_id": req_id,
            "endpoint": endpoint,
            "status_code": res.status_code,
            "duration": duration,
            "success": res.status_code == 200 and res.json().get("success", False),
            "error": None if res.status_code == 200 else res.text,
        }
    except Exception as e:
        duration = round(time.time() - start_time, 3)
        return {
            "req_id": req_id,
            "endpoint": "error",
            "status_code": 0,
            "duration": duration,
            "success": False,
            "error": str(e),
        }


async def run_batch(concurrency: int):
    print(f"\n==================================================")
    print(f"🚀 STRESS TEST BATCH: {concurrency} CONCURRENT REQUESTS")
    print(f"==================================================")
    
    async with httpx.AsyncClient() as client:
        tasks = [send_request(client, i + 1) for i in range(concurrency)]
        batch_start = time.time()
        results = await asyncio.gather(*tasks)
        total_time = round(time.time() - batch_start, 3)
        
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    durations = [r["duration"] for r in results]
    avg_dur = round(sum(durations) / len(durations), 3) if durations else 0
    min_dur = min(durations) if durations else 0
    max_dur = max(durations) if durations else 0
    
    print(f"Batch Execution Time: {total_time}s")
    print(f"Total Requests Sent:  {concurrency}")
    print(f"Successful (200 OK):  {success_count}")
    print(f"Failed / Errored:     {fail_count}")
    print(f"Latency (Min/Avg/Max): {min_dur}s / {avg_dur}s / {max_dur}s")
    
    if fail_count > 0:
        print("\n❌ Error Details:")
        for r in results:
            if not r["success"]:
                print(f"  Request #{r['req_id']}: {r['error']}")
    else:
        print("✅ All requests completed successfully with zero unhandled exceptions!")
    
    return {
        "concurrency": concurrency,
        "total_time": total_time,
        "success_count": success_count,
        "fail_count": fail_count,
        "min_dur": min_dur,
        "avg_dur": avg_dur,
        "max_dur": max_dur,
    }

async def main():
    res_5 = await run_batch(5)
    await asyncio.sleep(1.0)
    res_20 = await run_batch(20)
    
    print(f"\n==================================================")
    print(f"📊 FINAL STRESS TEST SUMMARY")
    print(f"==================================================")
    print(f"Level 1 (5 Concurrent):  {'PASS' if res_5['fail_count'] == 0 else 'FAIL'} (Avg Latency: {res_5['avg_dur']}s)")
    print(f"Level 2 (20 Concurrent): {'PASS' if res_20['fail_count'] == 0 else 'FAIL'} (Avg Latency: {res_20['avg_dur']}s)")
    print(f"==================================================")

if __name__ == "__main__":
    asyncio.run(main())
