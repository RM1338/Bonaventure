"""Synthetic inference must not require a demo bounding box for every finding."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from bonaventure import imaging


class MockImagingTests(unittest.TestCase):
    def test_unlocalised_findings_do_not_crash_or_get_invented_boxes(self):
        rng = Mock()
        rng.uniform.return_value = 0.3
        rng.choice.return_value = ["LUNG_MASS", "PLEURAL_EFFUSION"]
        image = Image.new("L", (64, 64), 128)
        with patch.object(imaging.np.random, "default_rng", return_value=rng):
            result = imaging._mock_analyze(image, "no-sidecar-test.png")
        self.assertNotIn("LUNG_MASS", result["localizations"])
        self.assertIn("PLEURAL_EFFUSION", result["localizations"])
        self.assertEqual(result["sources"][0]["scores"]["LUNG_MASS"], 0.82)

    def test_every_bundled_scan_supports_mock_inference(self):
        scans = Path(__file__).parents[1] / "sample_data/scans"
        for file in scans.iterdir():
            with self.subTest(file=file.name):
                image, _ = imaging.load_scan(file)
                self.assertTrue(imaging._mock_analyze(image, file)["sources"])
