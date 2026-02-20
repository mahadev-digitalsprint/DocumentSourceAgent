import unittest

from app.agents.classify_agent import _classify


class ClassifierRuleTests(unittest.TestCase):
    def test_financial_classification_with_confidence(self):
        category, doc_type, confidence, reasons = _classify(
            url="https://example.com/investor/annual-report-2025.pdf",
            local_path="annual-report-2025.pdf",
            first_page_text="Annual Report FY2025 consolidated financial statement",
        )
        self.assertEqual(category, "FINANCIAL")
        self.assertEqual(doc_type, "ANNUAL_REPORT")
        self.assertGreaterEqual(confidence, 0.6)
        self.assertGreater(len(reasons), 0)

    def test_low_confidence_for_ambiguous_document(self):
        category, doc_type, confidence, reasons = _classify(
            url="https://example.com/files/doc-123.pdf",
            local_path="doc-123.pdf",
            first_page_text="This is a general company publication with no clear filing keywords.",
        )
        self.assertIn(category, {"FINANCIAL", "NON_FINANCIAL"})
        self.assertLess(confidence, 0.6)
        self.assertTrue(doc_type == "OTHER" or len(reasons) == 0)


if __name__ == "__main__":
    unittest.main()
