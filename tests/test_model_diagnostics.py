import importlib.util
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("diagnose_models", Path(__file__).parents[1] / "scripts/diagnose_models.py")
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


class DiagnosticsTests(unittest.TestCase):
    def test_worker_failure_and_optional_skip_are_distinct(self):
        for code, expected in ((0, "passed"), (1, "failed"), (2, "skipped")):
            with patch.object(diagnostics.subprocess, "run", return_value=SimpleNamespace(returncode=code)) as run:
                result = diagnostics.run_check("Whisper-live", Path("scan.jpg"), 20)
                self.assertEqual(result["status"], expected)
                self.assertEqual(run.call_args.kwargs["timeout"], 20)
                self.assertEqual(run.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")

    def test_timeout_reported_without_preventing_next_check(self):
        with patch.object(diagnostics.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 20)):
            self.assertEqual(diagnostics.run_check("MedGemma-text", Path("scan.jpg"), 20)["status"], "timeout")

    def test_tied_missing_head_is_only_safe_when_weights_are_shared(self):
        def model(a, b):
            return SimpleNamespace(config=SimpleNamespace(tie_word_embeddings=True),
                                   get_input_embeddings=lambda: SimpleNamespace(weight=SimpleNamespace(data_ptr=lambda: a)),
                                   get_output_embeddings=lambda: SimpleNamespace(weight=SimpleNamespace(data_ptr=lambda: b)))
        diagnostics.check_tied(model(7, 7))
        with self.assertRaisesRegex(RuntimeError, "not shared"):
            diagnostics.check_tied(model(7, 8))
