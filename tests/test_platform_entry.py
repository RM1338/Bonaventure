"""The platform dispatcher must never import the other desktop implementation."""
import builtins
import sys
import types
import unittest
from unittest.mock import Mock, patch

from bonaventure import app


class PlatformEntryTests(unittest.TestCase):
    def check_platform(self, platform, selected, forbidden):
        launch = Mock()
        module = types.ModuleType(f"bonaventure.{selected}")
        module.main = launch
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if forbidden in name or forbidden in fromlist or name in ("AppKit", "objc", "PyObjCTools"):
                raise AssertionError(f"Unexpected desktop import: {name}")
            return original_import(name, globals, locals, fromlist, level)

        with patch.object(sys, "platform", platform), patch.dict(sys.modules, {module.__name__: module}), patch("builtins.__import__", guarded_import):
            app.main()
        launch.assert_called_once_with()

    def test_linux_rejected_before_native_import(self):
        with patch.object(sys, "platform", "linux"), patch("builtins.__import__", side_effect=AssertionError("Native import before rejection")):
            with self.assertRaisesRegex(SystemExit, "Omarchy/Linux"):
                app.main()

    def test_mac_imports_only_notch_desktop(self):
        self.check_platform("darwin", "macos_app", "linux_app")

    def test_windows_rejected_before_native_import(self):
        with patch.object(sys, "platform", "win32"), patch("builtins.__import__", side_effect=AssertionError("Native import before rejection")):
            with self.assertRaisesRegex(SystemExit, "windows branch"):
                app.main()


if __name__ == "__main__":
    unittest.main()
