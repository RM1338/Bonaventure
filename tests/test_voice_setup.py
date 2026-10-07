"""Check voice locations and optional setup checks without speech/model imports."""
import contextlib
import io
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch

from scripts import check_setup


class VoiceSetupTests(unittest.TestCase):
    def model_paths(self, root, home, **overrides):
        with patch.dict(os.environ, {"BV_MODELS_DIR": str(root), **overrides}, clear=True), patch("pathlib.Path.home", return_value=home):
            return runpy.run_path(str(Path(check_setup.paths.__file__)))

    def test_repo_voice_models_are_preferred(self):
        with tempfile.TemporaryDirectory() as folder:
            root, home = Path(folder) / "models", Path(folder) / "home"
            for name in ("whisper-base.en", "whisper-small.en"):
                (root / name).mkdir(parents=True)
                (root / name / "config.json").write_text("{}")
            result = self.model_paths(root, home)
            self.assertEqual(result["WHISPER_LIVE_DIR"], root / "whisper-base.en")
            self.assertEqual(result["WHISPER_FINAL_DIR"], root / "whisper-small.en")

    def test_legacy_home_models_still_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root, home = Path(folder) / "models", Path(folder) / "home"
            legacy = home / "bonaventure/models"
            for name in ("whisper-base.en", "whisper-small.en"):
                (legacy / name).mkdir(parents=True)
                (legacy / name / "config.json").write_text("{}")
            result = self.model_paths(root, home)
            self.assertEqual(result["WHISPER_LIVE_DIR"], legacy / "whisper-base.en")
            self.assertEqual(result["WHISPER_FINAL_DIR"], legacy / "whisper-small.en")

    def test_explicit_voice_paths_override_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = self.model_paths(root, root, BV_WHISPER_LIVE=str(root / "live"), BV_WHISPER=str(root / "final"))
            self.assertEqual(result["WHISPER_LIVE_DIR"], root / "live")
            self.assertEqual(result["WHISPER_FINAL_DIR"], root / "final")

    def check_voice(self, folder, missing_weights=False):
        directory = Path(folder)
        for name in ("config.json", "preprocessor_config.json", "tokenizer_config.json", "vocab.json", "merges.txt"):
            (directory / name).write_text("{}")
        if not missing_weights:
            (directory / "model.safetensors").write_bytes(b"weights")
        output = io.StringIO()
        with patch.object(check_setup.paths, "WHISPER_LIVE_DIR", directory), patch.object(check_setup.paths, "WHISPER_FINAL_DIR", directory), patch.object(check_setup.sys, "argv", ["check_setup.py", "--mock", "--voice"]), patch.object(check_setup.sys, "platform", "darwin"), patch.object(check_setup.importlib.util, "find_spec", return_value=S()), patch.object(check_setup.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"), contextlib.redirect_stdout(output):
            status = check_setup.main()
        return status, output.getvalue()

    def test_optional_voice_check_accepts_complete_local_models(self):
        with tempfile.TemporaryDirectory() as folder:
            status, output = self.check_voice(folder)
            self.assertEqual(status, 0)
            self.assertIn("Microphone recorder ffmpeg", output)

    def test_optional_voice_check_rejects_missing_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            status, output = self.check_voice(folder, missing_weights=True)
            self.assertEqual(status, 1)
            self.assertIn("MISSING Whisper live captions (base.en) weights", output)


if __name__ == "__main__":
    unittest.main()
