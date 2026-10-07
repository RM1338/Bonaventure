"""Execute actual launch scripts with fake Darwin/Homebrew/Python executables."""
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.install_macos import install_files


class MacLaunchEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project's files $(false)"
        self.root.mkdir()
        (self.root / "run.sh").write_text((Path(__file__).parents[1] / "run.sh").read_text())
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.environment = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", DYLD_FALLBACK_LIBRARY_PATH="/existing/lib")
        self.program("uname", 'printf "Darwin\\n"')
        self.program("brew", 'printf "/homebrew/prefix\\n"')
        python = self.root / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text('#!/bin/bash\nprintf "%s\\n" "$HF_HUB_OFFLINE" "$TRANSFORMERS_OFFLINE" "$PYTHONUNBUFFERED" "$DYLD_FALLBACK_LIBRARY_PATH" "$@"\n')
        python.chmod(0o755)

    def program(self, name, body):
        file = self.bin / name
        file.write_text("#!/bin/sh\n" + body + "\n")
        file.chmod(0o755)

    def run_script(self, *args):
        return subprocess.run(["/bin/bash", str(self.root / "run.sh"), *args], env=self.environment,
                              text=True, capture_output=True)

    def test_terminal_has_homebrew_offline_and_unbuffered_settings(self):
        result = self.run_script("BV-005")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["1", "1", "1", "/homebrew/prefix/lib:/existing/lib", "-m", "bonaventure.app", "BV-005"])

    def test_finder_wrapper_has_same_environment_without_reading_run_script(self):
        (self.root / "run.sh").unlink()  # background launch must not read the script
        home = self.base / "user home"
        app, _ = install_files(self.root, home)
        result = subprocess.run(["/bin/bash", str(app / "Contents/MacOS/Bonaventure")], env=self.environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = (home / "Library/Logs/Bonaventure/bonaventure.log").read_text().splitlines()
        self.assertEqual(lines[:4], ["1", "1", "1", "/homebrew/prefix/lib:/existing/lib"])
        self.assertEqual(lines[4:], ["-u", "-m", "bonaventure.app"])
        wrapper = (app / "Contents/MacOS/Bonaventure").read_text()
        self.assertNotIn(str(self.root / "run.sh"), wrapper)
        self.assertIn("export PYTHONPATH=", wrapper)

    def test_preflight_uses_same_environment(self):
        result = self.run_script("--check-runtime")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[:4], ["1", "1", "1", "/homebrew/prefix/lib:/existing/lib"])
        self.assertEqual(result.stdout.splitlines()[4:], ["-c", "import webview, AppKit, numpy, PIL, weasyprint"])

    def test_linux_rejected_before_python(self):
        self.program("uname", 'printf "Linux\\n"')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Use main for Omarchy/Linux", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_environment_reports_setup_instructions(self):
        (self.root / ".venv/bin/python").unlink()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MACOS_SETUP.md", result.stderr)
