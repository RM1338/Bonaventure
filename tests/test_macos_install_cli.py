"""Exercise install/login/uninstall flows in a temporary fake Mac home."""
import contextlib
import io
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import install_macos as installer


class InstallerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.root = Path(self.temp.name) / "project"
        python = self.root / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text("fake Python")
        (self.root / "run.sh").write_text("fake launch script")
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.connection.connect.side_effect = OSError("not running")
        self.app = self.home / "Applications/Bonaventure.app"
        self.agent = self.home / "Library/LaunchAgents" / f"{installer.LABEL}.plist"

    def run_installer(self, *args, platform="darwin", startup_ready=True):
        with patch.object(installer, "ROOT", self.root), patch("pathlib.Path.home", return_value=self.home), patch.object(installer.sys, "platform", platform), patch.object(installer.sys, "argv", ["install_macos.py", *args]), patch("socket.socket", return_value=self.connection), patch.object(installer.subprocess, "run") as run, patch.object(installer, "wait_for_launcher", return_value=startup_ready), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            installer.main()
        return [call.args[0] for call in run.call_args_list]

    def test_login_install_bootstraps_generated_agent(self):
        calls = self.run_installer()
        self.assertTrue((self.app / "Contents/Info.plist").exists())
        self.assertTrue(self.agent.exists())
        self.assertEqual(calls[-1][0:2], ["launchctl", "bootstrap"])
        self.assertEqual(calls[-1][-1], str(self.agent))

    def test_no_login_removes_old_agent_and_opens_app(self):
        installer.install_files(self.root, self.home)
        calls = self.run_installer("--no-login")
        self.assertFalse(self.agent.exists())
        self.assertEqual(calls[-1], ["open", str(self.app)])

    def test_uninstall_removes_only_owned_wrapper_and_agent(self):
        installer.install_files(self.root, self.home)
        marker = self.root / "preserve"
        marker.write_text("project and models stay")
        calls = self.run_installer("--uninstall")
        self.assertFalse(self.app.exists())
        self.assertFalse(self.agent.exists())
        self.assertTrue(marker.exists())
        self.assertEqual(calls[0][0:2], ["launchctl", "bootout"])

    def test_uninstall_rejects_unrelated_app_before_touching_agent(self):
        installer.install_files(self.root, self.home)
        info = self.app / "Contents/Info.plist"
        info.write_bytes(plistlib.dumps({"CFBundleIdentifier": "other.application"}))
        with self.assertRaisesRegex(RuntimeError, "identifier differs"):
            self.run_installer("--uninstall")
        self.assertTrue(self.agent.exists())
        self.assertTrue(self.app.exists())

    def test_running_instance_refuses_install(self):
        self.connection.connect.side_effect = None
        with self.assertRaises(SystemExit) as error:
            self.run_installer()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.app.exists())

    def test_unready_app_does_not_report_successful_start(self):
        with self.assertRaises(SystemExit) as error:
            self.run_installer(startup_ready=False)
        self.assertEqual(error.exception.code, 2)
        self.assertTrue(self.app.exists())

    def test_protected_checkout_stops_job_and_reports_move_without_installing(self):
        self.root = self.home / "Documents/Bonaventure"
        self.root.mkdir(parents=True)
        with self.assertRaises(SystemExit) as error:
            self.run_installer()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.app.exists())
        self.assertTrue(self.root.exists())

    def test_linux_refuses_installer_without_creating_files(self):
        with self.assertRaises(SystemExit) as error:
            self.run_installer(platform="linux")
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.home.exists())


if __name__ == "__main__":
    unittest.main()
