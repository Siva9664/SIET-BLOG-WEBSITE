import os
import sys
import json
import httpx
import asyncio

API_BASE = "http://localhost:8000/api/v1"
PDF_PATH = "/home/techpark-9/Downloads/Acheivements in AI LAB.pdf"
SAMPLE_PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads", "sample_event_photos")
if not os.path.exists(SAMPLE_PHOTOS_DIR):
    SAMPLE_PHOTOS_DIR = os.path.join(os.getcwd(), "backend", "uploads", "sample_event_photos")

async def main():
    # 1. Login as super admin
    async with httpx.AsyncClient(timeout=300.0) as client:
        login_res = await client.post(
            f"{API_BASE}/auth/login",
            json={"email": "admin@siet.ac.in", "password": "Admin@123"},
        )
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.status_code} {login_res.text}")
            return
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Authenticated successfully.")

        # 2. Prepare multipart upload
        if not os.path.exists(PDF_PATH):
            print(f"Error: {PDF_PATH} does not exist.")
            return

        photo_files = [
            "photo_nitish_hackerrank.jpg",
            "photo_mahibala_sarvam.jpg",
            "solana_frontier_hackathon.jpg",
            "meta_pytorch_hackathon.jpg",
            "india_innovates_mandapam.jpg",
        ]

        files_to_send = [
            ("file", ("Acheivements in AI LAB.pdf", open(PDF_PATH, "rb"), "application/pdf"))
        ]

        opened_photo_handles = []
        for p_name in photo_files:
            p_path = os.path.join(SAMPLE_PHOTOS_DIR, p_name)
            if os.path.exists(p_path):
                h = open(p_path, "rb")
                opened_photo_handles.append(h)
                files_to_send.append(("photos", (p_name, h, "image/jpeg")))

        data = {
            "event_name": "Artificial Intelligence Research Lab Accomplishments 2026",
            "event_date": "August 2026",
        }

        print(f"Sending auto-generation request with {len(files_to_send)-1} photos...")
        try:
            res = await client.post(
                f"{API_BASE}/admin/magazine/ai/auto-generate-from-file",
                headers=headers,
                data=data,
                files=files_to_send,
            )
        finally:
            files_to_send[0][1][1].close()
            for h in opened_photo_handles:
                h.close()

        print(f"Response status: {res.status_code}")
        if res.status_code != 200:
            print(f"Error response: {res.text}")
            return

        resp_data = res.json()
        payload = resp_data.get("data", resp_data)

        print("\n=== GENERATION OUTPUT ===")
        print(f"Magazine ID: {payload.get('magazine_id')}")
        print(f"Page Count: {payload.get('page_count')}")
        print(f"PDF URL: {payload.get('pdf_url')}")
        print(f"Photos Count: {payload.get('photos_count')}")
        print(f"Validation Summary: {json.dumps(payload.get('validation_summary'), indent=2)}")
        print("\n=== PHOTO ASSOCIATIONS ===")
        for assoc in payload.get("photo_associations", []):
            print(f"- Photo {assoc.get('photo_id')}: Event {assoc.get('event_id')} | Method: {assoc.get('association_method')} | Conf: {assoc.get('confidence')} | Evidence: {assoc.get('evidence')}")

        with open("uploads/live_generation_result.json", "w") as f:
            json.dump(payload, f, indent=2)
        print("\nSaved full result to uploads/live_generation_result.json")

if __name__ == "__main__":
    asyncio.run(main())
