"""Installer startup checks verify app readiness and reveal without toggling."""
import json
import socket
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from scripts import install_macos as installer


class StartupReadyTests(unittest.TestCase):
    def test_protected_folder_and_safe_developer_location(self):
        home = Path("/Users/test")
        for folder in ("Documents", "Desktop", "Downloads", "Library/Mobile Documents"):
            self.assertEqual(installer.protected_project_directory(home / folder / "nested/Bonaventure", home), folder)
        self.assertIsNone(installer.protected_project_directory(home / "Developer/Bonaventure", home))
        self.assertIsNone(installer.protected_project_directory(home / "Documents-other/Bonaventure", home))

    def test_probe_sends_status_and_reads_ready(self):
        connection = Mock()
        connection.recv.return_value = b'{"ready": true}'
        context = Mock()
        context.__enter__ = Mock(return_value=connection)
        context.__exit__ = Mock(return_value=False)
        with patch("socket.socket", return_value=context):
            self.assertTrue(installer.launcher_message("status"))
        connection.sendall.assert_called_once_with(b"status")

    def test_wait_reveals_only_when_launcher_ready(self):
        with patch.object(installer, "launcher_message", side_effect=[False, True, True]) as message, patch.object(installer.time, "sleep"):
            self.assertTrue(installer.wait_for_launcher())
        self.assertEqual([c.args[0] for c in message.call_args_list], ["status", "status", "show"])

    def test_connection_failure_retries_before_showing(self):
        with patch.object(installer, "launcher_message", side_effect=[OSError("starting"), True, True]) as message, patch.object(installer.time, "sleep"):
            self.assertTrue(installer.wait_for_launcher())
        self.assertEqual(message.call_count, 3)

    def test_missing_readiness_does_not_report_success(self):
        with patch.object(installer.time, "monotonic", side_effect=[0, 1, 3]), patch.object(installer.time, "sleep"), patch.object(installer, "launcher_message", return_value=False) as message:
            self.assertFalse(installer.wait_for_launcher(timeout=2))
        message.assert_called_once_with("status")
