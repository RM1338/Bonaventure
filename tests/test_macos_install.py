import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.install_macos import LABEL, install_files


class InstallerTests(unittest.TestCase):
    def test_installed_wrapper_handles_spaces_and_shell_characters(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "project's files $(false)"
            python = root / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
            python.chmod(0o755)
            (root / "run.sh").write_text("#!/bin/bash\nexec .venv/bin/python -m bonaventure.app\n")
            home = base / "user home"
            app, agent = install_files(root, home)
            executable = app / "Contents/MacOS/Bonaventure"
            subprocess.run(["bash", str(executable)], check=True)
            log = home / "Library/Logs/Bonaventure/bonaventure.log"
            self.assertEqual(log.read_text().splitlines(), ["-u", "-m", "bonaventure.app"])
            info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
            self.assertTrue(info["LSUIElement"])
            self.assertIn("dictate", info["NSMicrophoneUsageDescription"])
            service = plistlib.loads(agent.read_bytes())
            self.assertEqual(service["Label"], LABEL)
            self.assertEqual(service["ProgramArguments"], [str(executable)])
            self.assertTrue(service["RunAtLoad"])
            self.assertFalse(service["KeepAlive"]["SuccessfulExit"])

    def test_background_wrapper_adds_homebrew_to_a_minimal_login_path(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            root = home / "project"
            python = root / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text('#!/bin/bash\nprintf "%s" "$PATH"\n')
            python.chmod(0o755)
            (root / "run.sh").write_text("#!/bin/bash\nexec .venv/bin/python -m bonaventure.app\n")
            app, _ = install_files(root, home)
            subprocess.run(["/bin/bash", str(app / "Contents/MacOS/Bonaventure")],
                           env={"PATH": "/usr/bin:/bin"}, check=True)
            log = (home / "Library/Logs/Bonaventure/bonaventure.log").read_text()
            self.assertEqual(log, "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")

    def test_no_login_installs_only_app(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            app, agent = install_files(home / "project", home, login=False)
            self.assertTrue((app / "Contents/MacOS/Bonaventure").exists())
            self.assertFalse(agent.exists())

    def test_does_not_overwrite_an_unrelated_app(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            app = home / "Applications/Bonaventure.app"
            app.mkdir(parents=True)
            marker = app / "original"
            marker.write_text("keep")
            with self.assertRaisesRegex(RuntimeError, "Another app"):
                install_files(home / "project", home)
            self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
