"""
Unit tests for document ingestion module (PDF, DOCX, text).
Uses synthetic fixtures with zero external network dependencies.
"""

import io
import zipfile
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from ml.training.magazine.ingestion import (
    DocumentIngestion,
    sanitize_doc_id,
    compute_sha256,
    DocumentIngestionError,
)
from ml.training.magazine.schemas import DocumentRecord


def create_synthetic_png_bytes(color=(255, 0, 0), size=(32, 32)) -> bytes:
    """Generates in-memory PNG image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_synthetic_docx(target_path: Path, text_content: str, include_image: bool = True) -> None:
    """Creates a minimal valid synthetic .docx file with optional embedded image."""
    with zipfile.ZipFile(target_path, "w") as z:
        # [Content_Types].xml
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Default Extension="png" ContentType="image/png"/>\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            '</Types>'
        )
        z.writestr("[Content_Types].xml", content_types)

        # _rels/.rels
        dot_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
            '</Relationships>'
        )
        z.writestr("_rels/.rels", dot_rels)

        # word/_rels/document.xml.rels
        img_rel = ""
        if include_image:
            img_rel = '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>'
            z.writestr("word/media/image1.png", create_synthetic_png_bytes())

        doc_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  {img_rel}\n'
            '</Relationships>'
        )
        z.writestr("word/_rels/document.xml.rels", doc_rels)

        # word/document.xml
        import xml.sax.saxutils as saxutils
        escaped_text = saxutils.escape(text_content)
        img_xml = ""
        if include_image:
            img_xml = (
                '<w:r>'
                '  <w:drawing>'
                '    <a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                '            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                '            r:embed="rId2"/>'
                '  </w:drawing>'
                '</w:r>'
            )

        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            '            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            '  <w:body>\n'
            '    <w:p><w:r><w:t>' + escaped_text + '</w:t></w:r>' + img_xml + '</w:p>\n'
            '  </w:body>\n'
            '</w:document>'
        )
        z.writestr("word/document.xml", doc_xml)



class TestDocumentIngestion(unittest.TestCase):
    """Test suite for document ingestion interfaces."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.photos_dir = self.temp_path / "photos"
        self.ingestion = DocumentIngestion(photos_output_dir=self.photos_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_doc_id(self):
        self.assertEqual(sanitize_doc_id("SIET Magazine 2026-Vol.1.pdf"), "siet_magazine_2026_vol_1")
        self.assertEqual(sanitize_doc_id("Docx #Special & Characters!.docx"), "docx_special_characters")
        self.assertEqual(sanitize_doc_id(""), "doc_unknown")

    def test_docx_ingestion_with_image(self):
        docx_file = self.temp_path / "test_report.docx"
        text = "Department of Computer Science & Engineering organized an AI symposium on March 15, 2026."
        create_synthetic_docx(docx_file, text_content=text, include_image=True)

        record = self.ingestion.ingest_file(docx_file)

        self.assertIsInstance(record, DocumentRecord)
        self.assertEqual(record.doc_id, "test_report")
        self.assertEqual(record.file_type, "docx")
        self.assertEqual(record.total_pages, 1)
        self.assertIn("Computer Science", record.pages[0].text)

        # Check extracted photos
        self.assertEqual(len(record.pages[0].photos), 1)
        photo = record.pages[0].photos[0]
        self.assertEqual(photo.doc_id, "test_report")
        self.assertEqual(photo.page_number, 1)
        self.assertEqual(photo.width, 32)
        self.assertEqual(photo.height, 32)
        self.assertTrue(photo.sha256)

        # Verify photo saved to disk in photos_dir
        saved_file = self.photos_dir / photo.filename
        self.assertTrue(saved_file.exists(), "Extracted photo must be persisted on disk")

    def test_plaintext_ingestion(self):
        txt_file = self.temp_path / "annual_notes.txt"
        txt_file.write_text("Page 1 Content\x0cPage 2 Content\nWith more notes", encoding="utf-8")

        record = self.ingestion.ingest_file(txt_file)
        self.assertEqual(record.total_pages, 2)
        self.assertEqual(record.pages[0].text, "Page 1 Content")
        self.assertIn("Page 2 Content", record.pages[1].text)

    def test_unsupported_format_raises_error(self):
        unknown_file = self.temp_path / "data.xyz"
        unknown_file.write_text("invalid")
        with self.assertRaises(DocumentIngestionError):
            self.ingestion.ingest_file(unknown_file)


if __name__ == "__main__":
    unittest.main()
