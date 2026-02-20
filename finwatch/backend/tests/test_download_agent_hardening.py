import os
import tempfile
import unittest
import uuid

from app.agents.download_agent import _looks_like_pdf, _quarantine_file, _resolve_global_dedupe_path
from app.database import SessionLocal
from app.models import Company, DocumentRegistry


class DownloadAgentHardeningTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.query(DocumentRegistry).filter(DocumentRegistry.document_url.like("https://example.com/test-hardening/%")).delete()
        self.db.query(Company).filter(Company.company_slug.like("hardening-test-%")).delete()
        self.db.commit()
        self.db.close()

    def test_pdf_signature_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            valid_path = os.path.join(tmp, "valid.pdf")
            invalid_path = os.path.join(tmp, "invalid.pdf")
            with open(valid_path, "wb") as handle:
                handle.write(b"%PDF-1.7\nbinary")
            with open(invalid_path, "wb") as handle:
                handle.write(b"<html>not-a-pdf</html>")
            self.assertTrue(_looks_like_pdf(valid_path))
            self.assertFalse(_looks_like_pdf(invalid_path))

    def test_quarantine_file_moves_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "acme"
            source = os.path.join(tmp, "bad.pdf.part")
            with open(source, "wb") as handle:
                handle.write(b"bad content")
            target = _quarantine_file(tmp, slug, source, "invalid_signature")
            self.assertTrue(target)
            self.assertTrue(os.path.exists(target))
            self.assertFalse(os.path.exists(source))

    def test_global_hash_dedupe_resolution(self):
        company = Company(
            company_name="Hardening Co",
            company_slug=f"hardening-test-{uuid.uuid4().hex[:8]}",
            website_url="https://example.com",
            crawl_depth=2,
            active=True,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        with tempfile.TemporaryDirectory() as tmp:
            canonical = os.path.join(tmp, "canonical.pdf")
            with open(canonical, "wb") as handle:
                handle.write(b"%PDF-1.7\ncanonical")

            doc = DocumentRegistry(
                company_id=company.id,
                document_url=f"https://example.com/test-hardening/{uuid.uuid4().hex}",
                file_hash="abc123",
                local_path=canonical,
                doc_type="Unknown",
                status="NEW",
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)

            resolved = _resolve_global_dedupe_path(self.db, "abc123", exclude_doc_id=None)
            self.assertEqual(resolved, canonical)

            excluded = _resolve_global_dedupe_path(self.db, "abc123", exclude_doc_id=doc.id)
            self.assertIsNone(excluded)


if __name__ == "__main__":
    unittest.main()
