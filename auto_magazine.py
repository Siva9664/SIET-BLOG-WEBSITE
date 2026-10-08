#!/usr/bin/env python3
"""
auto_magazine.py - generate, approve, publish and verify a SIET magazine in one run.

Flow (uses only the existing API; no backend changes needed):
  1. login                      POST /api/v1/auth/login
  2. generate as DRAFT          POST /api/v1/admin/magazine/generate/end-to-end
  3. quality gate               QC must be valid on every page and score >= --min-score
  4. approve                    POST /api/v1/admin/magazine/{id}/approve
  5. publish                    POST /api/v1/admin/magazine/{id}/publish   (needs a SUPER_ADMIN login)
  6. verify on the public side  backend API + the frontend page + its images/PDF

If a gate fails the magazine stays an unpublished draft and the script exits non-zero
with the reason, so nothing broken ever reaches the public site.

Usage:
  export SIET_EMAIL=admin@siet.ac.in SIET_PASSWORD='...'
  python auto_magazine.py --doc event.docx --photos p0.jpg p1.jpg p2.jpg \
      --event-name "National Level AI Hackathon 2026" [--template SIET-Magazine-Template.docx]
"""
import argparse
import mimetypes
import os
import sys

import requests


def die(msg: str, code: int = 1):
    print(f"\nFAILED: {msg}")
    sys.exit(code)


def step(n: int, total: int, text: str):
    print(f"[{n}/{total}] {text}")


def unwrap(resp_json):
    """Accept both success-enveloped ({"data": ...}) and raw payloads."""
    if isinstance(resp_json, dict) and "data" in resp_json:
        return resp_json["data"]
    return resp_json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.getenv("SIET_API", "http://localhost:8000"))
    ap.add_argument("--site", default=os.getenv("SIET_SITE", "http://localhost:3000"))
    ap.add_argument("--email", default=os.getenv("SIET_EMAIL"))
    ap.add_argument("--password", default=os.getenv("SIET_PASSWORD"))
    ap.add_argument("--doc", help="source document (.docx/.pdf/.txt)")
    ap.add_argument("--notes", help="raw notes instead of a document")
    ap.add_argument("--photos", nargs="*", default=[])
    ap.add_argument("--template", action="append", default=[], help="template file(s), repeatable")
    ap.add_argument("--template-id", default=None)
    ap.add_argument("--event-name", default=None)
    ap.add_argument("--lab", default="AI & Data Science Lab")
    ap.add_argument("--lab-id", type=int, default=None,
                    help="target lab id (required for LAB_ADMINs with >1 lab membership)")
    ap.add_argument("--budget", type=int, default=5)
    ap.add_argument("--min-score", type=float, default=90.0, help="minimum overall QC score (0-100)")
    ap.add_argument("--no-llm", action="store_true", help="skip the LLM and use the deterministic fallback")
    ap.add_argument("--draft-only", action="store_true", help="generate + gate, but do not approve/publish")
    a = ap.parse_args()

    if not (a.email and a.password):
        die("set SIET_EMAIL and SIET_PASSWORD (or pass --email/--password)")
    if not (a.doc or a.notes):
        die("give --doc or --notes")
    for path in ([a.doc] if a.doc else []) + list(a.photos) + list(a.template):
        if not os.path.isfile(path):
            die(f"file not found: {path}")

    s = requests.Session()
    api = a.api.rstrip("/") + "/api/v1"

    step(1, 6, "logging in")
    r = s.post(f"{api}/auth/login", json={"email": a.email, "password": a.password}, timeout=30)
    if r.status_code != 200:
        die(f"login returned HTTP {r.status_code}: {r.text[:200]}")
    try:
        token = r.json().get("access_token")
    except Exception:
        token = None
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    else:
        print("      warning: no access_token in login response; falling back to cookies only")
    step(2, 6, "generating magazine as a draft (this can take a while with the LLM)")
    handles, files = [], []

    def add(field, path):
        h = open(path, "rb")
        handles.append(h)
        files.append((field, (os.path.basename(path), h,
                              mimetypes.guess_type(path)[0] or "application/octet-stream")))
    if a.doc:
        add("file", a.doc)
    for p in a.photos:
        add("photos", p)
    for t in a.template:
        add("templates", t)
    data = {
        "department_or_lab": a.lab,
        "target_page_budget": str(a.budget),
        "use_llm": "false" if a.no_llm else "true",
        "publish_immediately": "false",
    }
    if a.event_name:
        data["event_name"] = a.event_name
    if a.notes:
        data["raw_notes"] = a.notes
    if a.template_id:
        data["template_id"] = a.template_id
    if a.lab_id is not None:
        data["lab_id"] = str(a.lab_id)
    try:
        r = s.post(f"{api}/admin/magazine/generate/end-to-end", data=data, files=files, timeout=900)
    finally:
        for h in handles:
            h.close()
    if r.status_code != 200:
        die(f"generation returned HTTP {r.status_code}: {r.text[:400]}")
    d = unwrap(r.json())
    mag_id, slug = d.get("magazine_id"), d.get("slug")
    if not mag_id or not slug:
        die(f"generation response missing magazine_id/slug: {str(d)[:400]}")
    print(f"      magazine #{mag_id} '{d.get('title')}' - {d.get('total_pages')} pages,"
          f" score {d.get('overall_quality_score')}")

    step(3, 6, "quality gate")
    bad = [(i + 1, q.get("issues")) for i, q in enumerate(d.get("qc_reports", [])) if not q.get("is_valid")]
    if bad:
        die(f"QC failed on pages {bad}. Left as an unpublished draft (#{mag_id}).")
    if (d.get("overall_quality_score") or 0) < a.min_score:
        die(f"score {d.get('overall_quality_score')} < {a.min_score}."
            f" Left as an unpublished draft (#{mag_id}).")
    if d.get("total_pages", 0) < 1:
        die("no pages were produced")
    if (d.get("overall_quality_score") or 0) < 70:
        die(f"score {d.get('overall_quality_score')} would also fail the backend 0.70"
            " approve/publish gate.")
    print("      all pages valid, score OK")
    if a.draft_only:
        print(f"\nDraft #{mag_id} ready for manual review (slug: {slug}).")
        return

    step(4, 6, "approving")
    r = s.post(f"{api}/admin/magazine/{mag_id}/approve", timeout=30)
    if r.status_code != 200:
        die(f"approve returned HTTP {r.status_code}: {r.text[:300]}")

    step(5, 6, "publishing")
    r = s.post(f"{api}/admin/magazine/{mag_id}/publish", timeout=30)
    if r.status_code != 200:
        die(f"publish returned HTTP {r.status_code}: {r.text[:300]}"
            " (publish needs a SUPER_ADMIN account)")

    step(6, 6, "verifying on the public side")
    problems = []
    pub = requests.get(f"{api}/magazine/{slug}", timeout=30)
    if pub.status_code != 200:
        problems.append(f"public API detail -> HTTP {pub.status_code}")
        det = {}
    else:
        try:
            det = unwrap(pub.json())
        except Exception:
            det = {}
            problems.append("public API detail returned non-JSON")
    try:
        lst = requests.get(f"{api}/magazine", timeout=30).json()
    except Exception as e:
        lst = {}
        problems.append(f"public magazine list unreadable: {e}")
    raw_items = lst.get("items", [])
    if not raw_items and isinstance(lst.get("data"), dict):
        raw_items = lst["data"].get("items", [])
    if slug not in [i.get("slug") for i in raw_items if isinstance(i, dict)]:
        problems.append("not present in the public magazine list")
    site = a.site.rstrip("/")
    for path in (f"/magazine/{slug}", "/magazine"):
        try:
            rr = requests.get(site + path, timeout=120)
        except Exception as e:
            problems.append(f"frontend {path} -> request failed: {e}")
            continue
        if rr.status_code != 200:
            problems.append(f"frontend {path} -> HTTP {rr.status_code}")
    pages = det.get("pages", []) if isinstance(det, dict) else []
    if not pages:
        problems.append("public detail has no pages")
    for pg in pages[:3]:
        u = pg.get("imageUrl", "") or pg.get("image_url", "")
        if not u:
            problems.append("a page is missing its imageUrl")
            continue
        try:
            rr = requests.get(site + u, timeout=60)
        except Exception as e:
            problems.append(f"page image {u} via frontend -> request failed: {e}")
            continue
        if rr.status_code != 200 or "image" not in rr.headers.get("content-type", ""):
            problems.append(f"page image {u} via frontend -> HTTP {rr.status_code}")
    pdf_url = det.get("pdfUrl") or det.get("pdf_url") if isinstance(det, dict) else None
    if pdf_url:
        try:
            rr = requests.get(site + pdf_url, timeout=60)
        except Exception as e:
            problems.append(f"PDF via frontend -> request failed: {e}")
            rr = None
        if rr is not None and (rr.status_code != 200 or "pdf" not in rr.headers.get("content-type", "")):
            problems.append(f"PDF via frontend -> HTTP {rr.status_code}")
    else:
        problems.append("no pdfUrl on the public magazine")
    if problems:
        die("published, but the public side has problems:\n  - " + "\n  - ".join(problems))

    print(f"\nOK  magazine #{mag_id} is live: {site}/magazine/{slug}")


if __name__ == "__main__":
    main()

