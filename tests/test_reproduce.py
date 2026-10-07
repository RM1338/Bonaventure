"""Regression checks for demo failures and preservation of committed inputs."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("reproduce", ROOT / "scripts/reproduce.py")
reproduce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reproduce)


class ReproductionTests(unittest.TestCase):
    def test_real_run_rejects_automatic_mock_fallback(self):
        engine = SimpleNamespace(ready=lambda: True, mock=True, models={})
        with self.assertRaisesRegex(RuntimeError, "refusing automatic mock"):
            reproduce.wait_for_models(engine, False, 1)

    def test_partial_models_cannot_be_claimed_as_full_reproduction(self):
        engine = SimpleNamespace(ready=lambda: True, mock=False, models={"primary": object()})
        with self.assertRaisesRegex(RuntimeError, "verifier.*concepts.*reasoning.*segmentation"):
            reproduce.wait_for_models(engine, False, 1)

    def test_model_loading_timeout(self):
        engine = SimpleNamespace(ready=lambda: False)
        with patch.object(reproduce.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                reproduce.wait_for_models(engine, False, 1)

    def test_unknown_case_rejected_instead_of_running_entire_suite(self):
        with self.assertRaisesRegex(ValueError, "Unknown case"):
            reproduce.select_cases([dict(key="02")], ["20"])

    def test_numeric_selection_handles_single_digit_and_duplicates(self):
        rows = [dict(key="01"), dict(key="02")]
        self.assertEqual(reproduce.select_cases(rows, ["2", "02"]), [rows[1]])

    def test_failed_analysis_is_saved_as_failure_not_no_findings(self):
        from bonaventure import pipeline
        row = reproduce.select_cases(reproduce.catalogue("library"), ["02"])[0]
        fake = SimpleNamespace(id="BV-TEST", state="FAILED", result=None,
                               error={"code": "IMAGE_MODEL_FAILED"}, run=lambda engine: None,
                               progress=lambda: dict(state="FAILED"))
        with TemporaryDirectory() as tmp, patch.object(pipeline, "Case", return_value=fake):
            destination = Path(tmp) / "02"
            entry = reproduce.run_case(row, object(), destination, False)
            self.assertEqual(entry["state"], "FAILED")
            self.assertEqual(json.loads((destination / "error.json").read_text())["case_id"], "BV-TEST")
            self.assertFalse((destination / "result.json").exists())

    def test_pdf_failure_does_not_erase_successful_analysis(self):
        from bonaventure import pipeline, report
        row = reproduce.select_cases(reproduce.catalogue("library"), ["02"])[0]
        fake = SimpleNamespace(id="BV-TEST", state="REVIEW_READY", result={"findings": []},
                               error=None, run=lambda engine: None,
                               progress=lambda: dict(state="REVIEW_READY"))
        with TemporaryDirectory() as tmp, patch.object(pipeline, "Case", return_value=fake), \
                patch.object(report, "generate", side_effect=RuntimeError("PDF renderer failed")):
            destination = Path(tmp) / "02"
            entry = reproduce.run_case(row, object(), destination, True)
            self.assertEqual(entry["state"], "FAILED")
            self.assertTrue((destination / "result.json").exists())
            self.assertIn("PDF renderer failed", entry["error"])


if __name__ == "__main__":
    unittest.main()
