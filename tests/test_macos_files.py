"""File-panel ordering and cleanup without loading AppKit or models."""
import sys
import unittest
from types import SimpleNamespace as S
from unittest.mock import MagicMock, patch

from bonaventure.macos_files import choose_files


class FilePanelTests(unittest.TestCase):
    def setUp(self):
        self.panel, self.native, self.application = MagicMock(), MagicMock(), MagicMock()
        self.native.level.return_value = 26
        self.controls = S(file_dialog_open=False, file_picker=None, expanded=True, stopped=False)
        self.api = S(_mac_controls=self.controls, _launcher=S(native=self.native))
        appkit = S(NSOpenPanel=S(openPanel=lambda: self.panel), NSModalResponseOK=1, NSNormalWindowLevel=0,
                   NSApplication=S(sharedApplication=lambda: self.application))
        helper = S(AppHelper=S(callAfter=lambda fn: fn()))
        self.modules = patch.dict(sys.modules, {"AppKit": appkit, "PyObjCTools": helper})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def complete(self, response):
        def present(callback):
            self.assertTrue(self.controls.file_dialog_open)
            self.assertIs(self.controls.file_picker, self.panel)
            callback(response)
        self.panel.beginWithCompletionHandler_.side_effect = present

    def assert_released(self):
        self.assertFalse(self.controls.file_dialog_open)
        self.assertIsNone(self.controls.file_picker)
        self.native.makeKeyAndOrderFront_.assert_called_once_with(None)
        self.assertEqual([call.args[0] for call in self.native.setLevel_.call_args_list], [0, 26])

    def test_picker_is_above_launcher_and_returns_selected_files(self):
        self.complete(1)
        self.panel.URLs.return_value = [S(path=lambda: "/tmp/scan.png")]
        self.assertEqual(choose_files(self.api, False, ["png"]), ("/tmp/scan.png",))
        self.panel.setLevel_.assert_called_once_with(27)
        self.panel.setCanChooseDirectories_.assert_called_once_with(False)
        self.panel.setAllowsMultipleSelection_.assert_called_once_with(False)
        self.application.activateIgnoringOtherApps_.assert_called_once_with(True)
        self.assert_released()

    def test_cancel_restores_launcher_and_allows_another_picker(self):
        self.complete(0)
        self.assertIsNone(choose_files(self.api, True, ["pdf"]))
        self.assert_released()
        self.native.reset_mock()
        self.assertIsNone(choose_files(self.api, False, ["png"]))
        self.assert_released()

    def test_presentation_error_releases_waiting_worker_and_controls(self):
        self.panel.beginWithCompletionHandler_.side_effect = RuntimeError("panel unavailable")
        with self.assertRaisesRegex(RuntimeError, "panel unavailable"):
            choose_files(self.api, False, ["png"])
        self.assert_released()

    def test_result_error_releases_waiting_worker_and_controls(self):
        self.complete(1)
        self.panel.URLs.side_effect = RuntimeError("invalid selection")
        with self.assertRaisesRegex(RuntimeError, "invalid selection"):
            choose_files(self.api, False, ["png"])
        self.assert_released()

    def test_repeated_request_keeps_existing_picker(self):
        self.controls.file_dialog_open = True
        self.controls.file_picker = self.panel
        self.assertIsNone(choose_files(self.api, False, ["png"]))
        self.panel.beginWithCompletionHandler_.assert_not_called()
        self.assertTrue(self.controls.file_dialog_open)
        self.assertIs(self.controls.file_picker, self.panel)


if __name__ == "__main__":
    unittest.main()
