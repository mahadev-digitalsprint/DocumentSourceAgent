import tempfile
import unittest
from pathlib import Path

from app.services.file_organizer import infer_base_folder, move_to_classified_folder, target_subfolder


class FileOrganizerTests(unittest.TestCase):
    def test_target_subfolder(self):
        self.assertEqual(target_subfolder("FINANCIAL|QUARTERLY_RESULTS"), "QuarterlyReports")
        self.assertEqual(target_subfolder("FINANCIAL|ANNUAL_REPORT"), "AnnualReports")
        self.assertEqual(target_subfolder("FINANCIAL|EARNINGS_RELEASE"), "FinancialStatements")
        self.assertEqual(target_subfolder("NON_FINANCIAL|PRESS_RELEASE"), "NonFinancial")
        self.assertEqual(target_subfolder("UNKNOWN"), "Other")

    def test_infer_base_folder_from_existing_structure(self):
        path = Path("downloads") / "acme_ltd" / "Other" / "doc.pdf"
        base = infer_base_folder(path, "acme_ltd", "fallback_downloads")
        self.assertEqual(base, Path("downloads"))

    def test_move_to_classified_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "acme_ltd" / "Other"
            source.mkdir(parents=True, exist_ok=True)
            source_file = source / "quarterly.pdf"
            source_file.write_bytes(b"%PDF-1.7\n")

            new_path = move_to_classified_folder(
                local_path=str(source_file),
                company_slug="acme_ltd",
                doc_type_field="FINANCIAL|QUARTERLY_RESULTS",
                default_base=str(Path(tmp) / "downloads"),
                copy_mode=False,
            )
            self.assertTrue(Path(new_path).exists())
            self.assertIn(str(Path(tmp) / "acme_ltd" / "QuarterlyReports"), new_path)
            self.assertFalse(source_file.exists())

    def test_copy_mode_keeps_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "acme_ltd" / "Other"
            source.mkdir(parents=True, exist_ok=True)
            source_file = source / "annual.pdf"
            source_file.write_bytes(b"%PDF-1.7\n")

            new_path = move_to_classified_folder(
                local_path=str(source_file),
                company_slug="acme_ltd",
                doc_type_field="FINANCIAL|ANNUAL_REPORT",
                default_base=str(Path(tmp) / "downloads"),
                copy_mode=True,
            )
            self.assertTrue(Path(new_path).exists())
            self.assertTrue(source_file.exists())
            self.assertIn(str(Path(tmp) / "acme_ltd" / "AnnualReports"), new_path)


if __name__ == "__main__":
    unittest.main()
