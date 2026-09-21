"""
Document ingestion module for PDF and DOCX magazine sources.
Extracts text, page boundaries, page numbers, and embedded photos
while strictly preserving document provenance and visual order.
"""

from __future__ import annotations

import os
import re
import io
import shutil
import hashlib
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image

from .schemas import DocumentRecord, PageData, PhotoItem


def compute_sha256(filepath_or_bytes: Path | bytes) -> str:
    """Computes SHA-256 hex digest for a file or raw bytes."""
    h = hashlib.sha256()
    if isinstance(filepath_or_bytes, (str, Path)):
        with open(filepath_or_bytes, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
    else:
        h.update(filepath_or_bytes)
    return h.hexdigest()


def sanitize_doc_id(name: str) -> str:
    """Derives a clean document ID from a file name."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", Path(name).stem)
    clean = re.sub(r"_+", "_", clean).strip("_").lower()
    return clean or "doc_unknown"



class DocumentIngestionError(Exception):
    """Raised when document ingestion fails."""
    pass


class DocumentIngestion:
    """
    Ingests PDF and DOCX documents, extracting text per page and embedded images.
    Preserves document/page provenance.
    """

    def __init__(self, photos_output_dir: Optional[Path] = None):
        self.photos_output_dir = Path(photos_output_dir) if photos_output_dir else None
        if self.photos_output_dir:
            self.photos_output_dir.mkdir(parents=True, exist_ok=True)

    def ingest_file(self, file_path: Path) -> DocumentRecord:
        file_path = Path(file_path)
        if not file_path.exists():
            raise DocumentIngestionError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self.ingest_pdf(file_path)
        elif ext in {".docx", ".docm"}:
            return self.ingest_docx(file_path)
        elif ext in {".txt", ".md", ".json"}:
            return self.ingest_plaintext(file_path)
        else:
            raise DocumentIngestionError(f"Unsupported file format: {ext} ({file_path})")

    def ingest_plaintext(self, file_path: Path) -> DocumentRecord:
        """Ingests plain text / markdown files, treating form-feed (\\x0c) as page breaks."""
        content = file_path.read_text(encoding="utf-8", errors="replace")
        doc_id = sanitize_doc_id(file_path.name)
        sha = compute_sha256(file_path)

        raw_pages = content.split("\x0c") if "\x0c" in content else [content]
        pages: List[PageData] = []
        for idx, page_str in enumerate(raw_pages, start=1):
            pages.append(PageData(page_number=idx, text=page_str.strip(), photos=[]))

        return DocumentRecord(
            doc_id=doc_id,
            filename=file_path.name,
            file_type="txt",
            total_pages=len(pages),
            sha256=sha,
            pages=pages,
        )

    # -------------------------------------------------------------------------
    # DOCX Ingestion (Pure Python using zipfile and XML)
    # -------------------------------------------------------------------------
    def ingest_docx(self, file_path: Path) -> DocumentRecord:
        doc_id = sanitize_doc_id(file_path.name)
        doc_sha = compute_sha256(file_path)

        try:
            with zipfile.ZipFile(file_path, "r") as z:
                # 1. Read relationships to map rId -> media file
                rels_map = self._parse_docx_rels(z)

                # 2. Read document.xml
                doc_xml_bytes = z.read("word/document.xml")
                root = ET.fromstring(doc_xml_bytes)

                # XML namespaces
                ns = {
                    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                    "v": "urn:schemas-microsoft-com:vml",
                }

                # 3. Iterate through body children and track pages
                pages_data: List[Dict[str, Any]] = [{"text_chunks": [], "images": []}]
                current_page_idx = 1

                body = root.find("w:body", ns)
                if body is None:
                    pages_data[0]["text_chunks"].append("")
                else:
                    for elem in body:
                        tag = elem.tag.split("}")[-1]

                        # Check for page break inside paragraph
                        if tag == "p":
                            # Check if paragraph has a page break
                            has_page_break = False
                            for br in elem.findall(".//w:br", ns):
                                if br.attrib.get(f"{{{ns['w']}}}type") == "page":
                                    has_page_break = True
                            if elem.findall(".//w:lastRenderedPageBreak", ns):
                                has_page_break = True

                            # Extract text
                            texts = [t.text for t in elem.findall(".//w:t", ns) if t.text]
                            p_text = "".join(texts).strip()
                            if p_text:
                                pages_data[current_page_idx - 1]["text_chunks"].append(p_text)

                            # Extract drawings / images in this paragraph
                            for blip in elem.findall(".//a:blip", ns):
                                r_id = blip.attrib.get(f"{{{ns['r']}}}embed")
                                if r_id and r_id in rels_map:
                                    media_path = rels_map[r_id]
                                    pages_data[current_page_idx - 1]["images"].append(media_path)

                            # Legacy VML images
                            for imagedata in elem.findall(".//v:imagedata", ns):
                                r_id = imagedata.attrib.get(f"{{{ns['r']}}}id")
                                if r_id and r_id in rels_map:
                                    media_path = rels_map[r_id]
                                    pages_data[current_page_idx - 1]["images"].append(media_path)

                            if has_page_break:
                                current_page_idx += 1
                                pages_data.append({"text_chunks": [], "images": []})

                        elif tag == "sectPr":
                            # Section break could imply new page if subsequent content exists
                            pass

                # Save extracted images and construct PageData
                pages: List[PageData] = []
                for p_idx, p_info in enumerate(pages_data, start=1):
                    full_text = "\n\n".join(p_info["text_chunks"])
                    extracted_photos: List[PhotoItem] = []

                    for img_order, media_name in enumerate(p_info["images"]):
                        # Extract image file from zip
                        zip_entry = f"word/{media_name}" if not media_name.startswith("word/") else media_name
                        if zip_entry in z.namelist():
                            img_data = z.read(zip_entry)
                            photo_item = self._persist_photo(
                                doc_id=doc_id,
                                page_number=p_idx,
                                order_on_page=img_order,
                                raw_bytes=img_data,
                                original_name=Path(media_name).name,
                            )
                            extracted_photos.append(photo_item)

                    pages.append(PageData(page_number=p_idx, text=full_text, photos=extracted_photos))

                # Handle empty document case
                if not pages:
                    pages.append(PageData(page_number=1, text="", photos=[]))

                return DocumentRecord(
                    doc_id=doc_id,
                    filename=file_path.name,
                    file_type="docx",
                    total_pages=len(pages),
                    sha256=doc_sha,
                    pages=pages,
                )

        except Exception as e:
            raise DocumentIngestionError(f"Error parsing DOCX {file_path}: {e}") from e

    def _parse_docx_rels(self, z: zipfile.ZipFile) -> Dict[str, str]:
        """Parses word/_rels/document.xml.rels to map rId -> target media path."""
        rels = {}
        rels_path = "word/_rels/document.xml.rels"
        if rels_path in z.namelist():
            try:
                tree = ET.fromstring(z.read(rels_path))
                for rel in tree:
                    r_id = rel.attrib.get("Id")
                    target = rel.attrib.get("Target")
                    if r_id and target:
                        rels[r_id] = target
            except Exception:
                pass
        return rels

    # -------------------------------------------------------------------------
    # PDF Ingestion (pdftotext + pdfimages with fallback)
    # -------------------------------------------------------------------------
    def ingest_pdf(self, file_path: Path) -> DocumentRecord:
        doc_id = sanitize_doc_id(file_path.name)
        doc_sha = compute_sha256(file_path)

        has_pdftotext = shutil.which("pdftotext") is not None
        has_pdfimages = shutil.which("pdfimages") is not None

        if has_pdftotext:
            return self._ingest_pdf_poppler(file_path, doc_id, doc_sha, has_pdfimages)
        else:
            return self._ingest_pdf_pure_python(file_path, doc_id, doc_sha)

    def _ingest_pdf_poppler(
        self, file_path: Path, doc_id: str, doc_sha: str, has_pdfimages: bool
    ) -> DocumentRecord:
        """Uses poppler CLI tools for robust layout-preserved text and image extraction."""
        # 1. Run pdftotext with layout preservation
        try:
            res = subprocess.run(
                ["pdftotext", "-layout", str(file_path), "-"],
                capture_output=True,
                check=True,
            )
            raw_stdout = res.stdout.decode("utf-8", errors="replace")
        except subprocess.CalledProcessError as e:
            raise DocumentIngestionError(f"pdftotext execution failed for {file_path}: {e}")

        # Pages are delimited by form feed character (\x0c)
        page_texts = raw_stdout.split("\x0c")
        if page_texts and page_texts[-1].strip() == "":
            page_texts.pop()  # trailing form-feed

        total_pages = max(1, len(page_texts))

        # 2. Extract images per page if pdfimages is available and photos dir is configured
        page_photos: Dict[int, List[PhotoItem]] = {p: [] for p in range(1, total_pages + 1)}

        if has_pdfimages and self.photos_output_dir:
            temp_dir = self.photos_output_dir / f"_tmp_{doc_id}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            try:
                # pdfimages -png file prefix
                prefix = temp_dir / "img"
                subprocess.run(
                    ["pdfimages", "-png", str(file_path), str(prefix)],
                    capture_output=True,
                    check=False,
                )

                # List images with pdfimages -list to get exact page mapping
                list_res = subprocess.run(
                    ["pdfimages", "-list", str(file_path)],
                    capture_output=True,
                    check=False,
                )
                list_stdout = list_res.stdout.decode("utf-8", errors="replace")
                image_page_map = self._parse_pdfimages_list(list_stdout)

                # Match extracted files in temp_dir
                extracted_files = sorted(temp_dir.glob("img-*.png"))
                for idx, img_file in enumerate(extracted_files):
                    # Get corresponding page from map if possible, else 1
                    page_num = image_page_map[idx] if idx < len(image_page_map) else 1
                    page_num = min(max(1, page_num), total_pages)

                    img_bytes = img_file.read_bytes()
                    photo_item = self._persist_photo(
                        doc_id=doc_id,
                        page_number=page_num,
                        order_on_page=len(page_photos[page_num]),
                        raw_bytes=img_bytes,
                        original_name=img_file.name,
                    )
                    page_photos[page_num].append(photo_item)

            finally:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)

        pages: List[PageData] = []
        for p_idx in range(1, total_pages + 1):
            p_text = page_texts[p_idx - 1].strip() if p_idx - 1 < len(page_texts) else ""
            pages.append(PageData(
                page_number=p_idx,
                text=p_text,
                photos=page_photos.get(p_idx, [])
            ))

        return DocumentRecord(
            doc_id=doc_id,
            filename=file_path.name,
            file_type="pdf",
            total_pages=total_pages,
            sha256=doc_sha,
            pages=pages,
        )

    def _parse_pdfimages_list(self, output: str) -> List[int]:
        """Parses stdout of 'pdfimages -list' to extract page numbers in order of images."""
        pages = []
        lines = output.strip().splitlines()
        # Header is usually first 2 lines
        for line in lines[2:]:
            parts = line.strip().split()
            if parts and parts[0].isdigit():
                page_num = int(parts[0])
                pages.append(page_num)
        return pages

    def _ingest_pdf_pure_python(
        self, file_path: Path, doc_id: str, doc_sha: str
    ) -> DocumentRecord:
        """Pure-python fallback parser for synthetic/minimal PDF documents."""
        raw_bytes = file_path.read_bytes()
        text = ""
        # Find BT ... ET blocks
        bt_blocks = re.findall(rb"BT\s*(.*?)\s*ET", raw_bytes, re.DOTALL)
        extracted_strings = []
        for block in bt_blocks:
            # Matches strings in parentheses: (Hello World)
            strings = re.findall(rb"\((.*?)\)", block)
            for s in strings:
                extracted_strings.append(s.decode("latin1", errors="replace"))

        text = "\n".join(extracted_strings)
        pages = [PageData(page_number=1, text=text.strip(), photos=[])]

        return DocumentRecord(
            doc_id=doc_id,
            filename=file_path.name,
            file_type="pdf",
            total_pages=1,
            sha256=doc_sha,
            pages=pages,
        )

    # -------------------------------------------------------------------------
    # Helper: Save photo and construct metadata
    # -------------------------------------------------------------------------
    def _persist_photo(
        self,
        doc_id: str,
        page_number: int,
        order_on_page: int,
        raw_bytes: bytes,
        original_name: str,
    ) -> PhotoItem:
        """Saves image bytes to photos directory, calculates dimensions & hash."""
        sha = compute_sha256(raw_bytes)
        ext = Path(original_name).suffix.lstrip(".").lower() or "png"
        photo_id = f"{doc_id}_p{page_number}_img{order_on_page}"
        filename = f"{photo_id}.{ext}"

        width, height = None, None
        fmt = ext
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                width, height = img.size
                fmt = (img.format or ext).lower()
        except Exception:
            pass

        rel_path = f"photos/{filename}"
        if self.photos_output_dir:
            dest_file = self.photos_output_dir / filename
            dest_file.write_bytes(raw_bytes)

        return PhotoItem(
            photo_id=photo_id,
            doc_id=doc_id,
            page_number=page_number,
            relative_path=rel_path,
            filename=filename,
            width=width,
            height=height,
            sha256=sha,
            format=fmt,
            order_on_page=order_on_page,
        )
