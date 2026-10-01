"""Live End-to-End Test for Magazine Pipeline with NO Mocks.

1. Tests LLM keys and SigLIP model loading, reports missing configs.
2. Takes real sample DOCX from uploads/, submits via actual API endpoint.
3. Confirms PDF exists on disk, physical page count, file size, QC score,
   and verifies that /magazine/<slug> serves it.
4. Reports exact status, timing, and full error tracebacks if any failure occurs.
"""

import base64
import json
import os
import sys
import time
import traceback
from pathlib import Path

import fitz  # PyMuPDF
import httpx

from app.core.config import settings
from app.core.security import create_access_token


def run_test():
    report = {
        "step_1_config": {},
        "step_2_submission": {},
        "step_3_verification": {},
        "step_4_errors": [],
    }

    print("=" * 80)
    print("🚀 REAL END-TO-END MAGAZINE PIPELINE TEST (NO MOCKS)")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # STEP 1: Verify Configuration, LLM, SigLIP
    # --------------------------------------------------------------------------
    print("\n--- [STEP 1: CONFIGURATION & MODEL VERIFICATION] ---")
    
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    llm_provider = os.getenv("MAGAZINE_LLM_PROVIDER", "auto")
    ollama_model = getattr(settings, "MAGAZINE_OLLAMA_MODEL", "qwen3:4b")
    vision_model = getattr(settings, "MAGAZINE_VISION_MODEL", "google/siglip-base-patch16-224")

    config_info = {
        "GEMINI_API_KEY": "SET" if gemini_key else "MISSING / NOT SET",
        "OPENAI_API_KEY": "SET" if openai_key else "MISSING / NOT SET",
        "MAGAZINE_LLM_PROVIDER": llm_provider,
        "MAGAZINE_OLLAMA_MODEL": ollama_model,
        "MAGAZINE_VISION_MODEL": vision_model,
    }
    report["step_1_config"] = config_info
    print("Configuration Overview:")
    for k, v in config_info.items():
        print(f"  - {k}: {v}")

    # Check Ollama connectivity
    ollama_active = False
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        if r.status_code == 200:
            ollama_active = True
            models = [m.get("name") for m in r.json().get("models", [])]
            report["step_1_config"]["ollama_active"] = True
            report["step_1_config"]["ollama_models"] = models
            print(f"  - Ollama local server: REACHABLE (Available models: {models})")
    except Exception as e:
        report["step_1_config"]["ollama_active"] = False
        report["step_1_config"]["ollama_error"] = str(e)
        print(f"  - Ollama local server: UNREACHABLE ({e})")

    # Check SigLIP loading
    siglip_loaded = False
    try:
        from app.modules.magazine.vision_embedder import SiglipVisionEmbedder
        embedder = SiglipVisionEmbedder()
        embedder._ensure_loaded()
        siglip_loaded = embedder._model is not None and embedder._processor is not None
        report["step_1_config"]["siglip_loaded"] = siglip_loaded
        print(f"  - SigLIP Vision Model ({vision_model}): LOADED SUCCESSFULLY")
    except Exception as e:
        report["step_1_config"]["siglip_loaded"] = False
        report["step_1_config"]["siglip_error"] = str(e)
        print(f"  - SigLIP Vision Model: FAILED TO LOAD ({e})")
        report["step_4_errors"].append({"stage": "siglip_load", "error": str(e), "traceback": traceback.format_exc()})

    # --------------------------------------------------------------------------
    # STEP 2: Submit Sample DOCX via Actual API Endpoint
    # --------------------------------------------------------------------------
    print("\n--- [STEP 2: API SUBMISSION OF REAL DOCX] ---")
    docx_rel_path = "uploads/documents/doc_140072806962439690_469e9b.docx"
    if not os.path.exists(docx_rel_path):
        docx_rel_path = "uploads/magazines/auto_generated_1787997045_ebed67.docx"
    
    print(f"Using Sample DOCX: {docx_rel_path} ({os.path.getsize(docx_rel_path)} bytes)")

    # Generate real signed Admin JWT token
    token = create_access_token("1", "SUPER_ADMIN")
    headers = {
        "Authorization": f"Bearer {token}",
    }

    api_url = "http://localhost:8000/api/v1/admin/magazine/generate/end-to-end"
    print(f"Submitting to Endpoint: POST {api_url} with use_llm=True (Ollama {ollama_model})...")

    t_start = time.time()
    try:
        with open(docx_rel_path, "rb") as f_in:
            files = {
                "file": (os.path.basename(docx_rel_path), f_in, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            }
            data = {
                "event_name": "SIET AI & Innovation Symposium",
                "department_or_lab": "AI & Data Science Lab",
                "target_page_budget": "4",
                "publish_immediately": "true",
                "use_llm": "true",
                "max_qc_attempts": "3",
            }
            # Timeout set to 300 seconds for complete real LLM + SigLIP + PyMuPDF generation
            with httpx.Client(timeout=300.0) as client:
                res = client.post(api_url, headers=headers, data=data, files=files)
        
        duration = round(time.time() - t_start, 2)
        print(f"API Response Received in {duration}s! HTTP Status Code: {res.status_code}")
        
        report["step_2_submission"]["status_code"] = res.status_code
        report["step_2_submission"]["duration_seconds"] = duration

        if res.status_code != 200:
            err_text = res.text
            print(f"❌ API Submission Failed! Status: {res.status_code}")
            print(f"Error Body:\n{err_text[:1000]}")
            report["step_2_submission"]["error"] = err_text
            report["step_4_errors"].append({
                "stage": "api_submission",
                "status_code": res.status_code,
                "error": err_text,
            })
            return report

        payload = res.json()
        mag_data = payload.get("data", {})
        report["step_2_submission"]["data"] = mag_data
        print(f"✅ API Submission Successful!")
        print(f"  - Magazine ID: {mag_data.get('magazine_id')}")
        print(f"  - Title: {mag_data.get('title')}")
        print(f"  - Slug: {mag_data.get('slug')}")
        print(f"  - Total Pages: {mag_data.get('total_pages')}")
        print(f"  - Status: {mag_data.get('status')}")
        print(f"  - Overall QC Score: {mag_data.get('overall_quality_score')}")
        print(f"  - PDF URL: {mag_data.get('pdf_url')}")

    except Exception as e:
        duration = round(time.time() - t_start, 2)
        tb = traceback.format_exc()
        print(f"❌ Exception during API Submission after {duration}s: {e}")
        print(tb)
        report["step_2_submission"]["exception"] = str(e)
        report["step_2_submission"]["traceback"] = tb
        report["step_4_errors"].append({"stage": "api_submission_exception", "error": str(e), "traceback": tb})
        return report

    # --------------------------------------------------------------------------
    # STEP 3: Confirm PDF Exists, Physical Pages, Size, QC, & Public Serving
    # --------------------------------------------------------------------------
    print("\n--- [STEP 3: PDF ARTIFACT & PUBLIC ENDPOINT VERIFICATION] ---")
    slug = mag_data.get("slug")
    pdf_rel_url = mag_data.get("pdf_url") or ""
    
    # Path on disk
    clean_pdf_path = pdf_rel_url.lstrip("/")
    pdf_on_disk = os.path.exists(clean_pdf_path)
    report["step_3_verification"]["pdf_path_checked"] = clean_pdf_path
    report["step_3_verification"]["pdf_exists_on_disk"] = pdf_on_disk

    if pdf_on_disk:
        file_size_bytes = os.path.getsize(clean_pdf_path)
        report["step_3_verification"]["file_size_bytes"] = file_size_bytes
        print(f"  - PDF File Exists on Disk: YES ({clean_pdf_path})")
        print(f"  - PDF File Size: {file_size_bytes:,} bytes ({round(file_size_bytes / 1024, 2)} KB)")

        try:
            doc = fitz.open(clean_pdf_path)
            physical_pages = len(doc)
            report["step_3_verification"]["physical_page_count"] = physical_pages
            print(f"  - Physical PDF Page Count (PyMuPDF): {physical_pages} pages")
            doc.close()
        except Exception as e:
            print(f"  - ❌ PyMuPDF could not read generated PDF: {e}")
            report["step_3_verification"]["fitz_error"] = str(e)
            report["step_4_errors"].append({"stage": "fitz_read", "error": str(e), "traceback": traceback.format_exc()})
    else:
        print(f"  - ❌ PDF File DOES NOT EXIST at: {clean_pdf_path}")
        report["step_4_errors"].append({"stage": "pdf_existence", "error": f"PDF not found at {clean_pdf_path}"})

    # Verify Public API endpoint: GET /api/v1/magazine/<slug>
    public_api_url = f"http://localhost:8000/api/v1/magazine/{slug}"
    print(f"\nTesting Public API Endpoint: GET {public_api_url} ...")
    try:
        with httpx.Client(timeout=10.0) as client:
            pub_res = client.get(public_api_url)
            report["step_3_verification"]["public_api_status"] = pub_res.status_code
            if pub_res.status_code == 200:
                pub_data = pub_res.json().get("data", {})
                print(f"  - Public API Status: 200 OK")
                print(f"  - Public API Title: '{pub_data.get('title')}'")
                print(f"  - Public API Pages Count: {len(pub_data.get('pages', []))}")
                print(f"  - Public API TOC Count: {len(pub_data.get('toc_entries', []))}")
                report["step_3_verification"]["public_api_data"] = {
                    "title": pub_data.get("title"),
                    "page_count": len(pub_data.get("pages", [])),
                    "toc_count": len(pub_data.get("toc_entries", [])),
                    "download_url": pub_data.get("pdf_url"),
                }
            else:
                print(f"  - ❌ Public API returned {pub_res.status_code}: {pub_res.text[:300]}")
                report["step_4_errors"].append({"stage": "public_api_fetch", "status": pub_res.status_code, "body": pub_res.text})
    except Exception as e:
        print(f"  - ❌ Public API call failed: {e}")
        report["step_4_errors"].append({"stage": "public_api_exception", "error": str(e), "traceback": traceback.format_exc()})

    # Verify Next.js frontend route: GET http://localhost:3000/magazine/<slug>
    frontend_url = f"http://localhost:3000/magazine/{slug}"
    print(f"\nTesting Frontend Web Reader Route: GET {frontend_url} ...")
    try:
        with httpx.Client(timeout=15.0) as client:
            front_res = client.get(frontend_url)
            report["step_3_verification"]["frontend_status"] = front_res.status_code
            if front_res.status_code == 200:
                print(f"  - Frontend Web Reader Status: 200 OK (Content Length: {len(front_res.text)} bytes)")
                report["step_3_verification"]["frontend_serves"] = True
            else:
                print(f"  - ⚠️ Frontend Web Reader returned {front_res.status_code}")
                report["step_3_verification"]["frontend_serves"] = False
    except Exception as e:
        print(f"  - ⚠️ Frontend Web Reader check error (frontend dev server might be warming up): {e}")
        report["step_3_verification"]["frontend_error"] = str(e)

    out_file = "uploads/magazines/live_e2e_test_report.json"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull Test Report saved to: {out_file}")
    print("=" * 80)
    return report


if __name__ == "__main__":
    run_test()
