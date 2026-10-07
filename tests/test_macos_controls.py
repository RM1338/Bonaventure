"""Exercise the actual menu controller with fake AppKit events and clock."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch

from bonaventure.launcher_hover import HoverIntent


class ControllerTests(unittest.TestCase):
    def setUp(self):
        frame = S(origin=S(x=0, y=0), size=S(width=1512, height=982))
        visible = S(origin=S(x=0, y=0), size=S(width=1512, height=944))
        screen = S(frame=lambda: frame, visibleFrame=lambda: visible, safeAreaInsets=lambda: S(top=38))
        self.mouse = S(x=756, y=970)
        self.appkit = S(NSObject=object, NSEventTypeLeftMouseDown=1,
                        NSScreen=S(screens=lambda: [screen]),
                        NSEvent=S(mouseLocation=lambda: self.mouse, removeMonitor_=Mock()),
                        NSStatusBar=S(systemStatusBar=lambda: S(removeStatusItem_=Mock())))
        modules = {"AppKit": self.appkit, "objc": S(python_method=lambda fn: fn),
                   "Foundation": S(NSRunLoop=None, NSRunLoopCommonModes=None, NSTimer=None),
                   "PyObjCTools": S(AppHelper=S(callAfter=lambda fn, *args: fn(*args)))}
        self.patches = patch.dict(sys.modules, modules)
        self.patches.start()
        self.addCleanup(self.patches.stop)
        spec = importlib.util.spec_from_file_location("bonaventure._controls_test", Path(__file__).parents[1] / "bonaventure/macos_controls.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.controls = self.module.MenuBarController()
        self.native = Mock()
        self.native.frame.return_value = S(origin=S(x=426, y=704), size=S(width=660, height=278))
        self.controls.api = S(_launcher_ready=True, _launcher=S(native=self.native))
        self.controls.file_dialog_open = False
        self.controls.stopped = False
        self.controls.expanded = False
        self.controls.pinned = False
        self.controls.suppressed = False
        self.controls.view = "idle"
        self.controls.intent = HoverIntent()
        self.controls.javascript = Mock()
        self.controls.toggle_item = Mock()
        self.controls.hotkey = Mock()

    def poll(self, now):
        with patch.object(self.module.time, "monotonic", return_value=now):
            self.controls.pollHover_(None)

    def test_shortcut_reveals_and_closes_without_early_focus_release(self):
        self.controls.toggleLauncher_(None)
        self.assertTrue(self.controls.expanded)
        self.native.makeKeyAndOrderFront_.assert_called_once()
        self.controls.toggleLauncher_(None)
        self.assertFalse(self.controls.expanded)
        self.native.resignKeyWindow.assert_not_called()
        self.assertEqual(self.controls.javascript.call_count, 2)

    def test_shortcut_does_not_run_before_bridge_ready(self):
        self.controls.api._launcher_ready = False
        self.controls.toggleLauncher_(None)
        self.controls.javascript.assert_not_called()

    def test_picker_pauses_hover_shortcut_and_escape_handling(self):
        self.controls.file_dialog_open = True
        self.poll(0)
        self.poll(1)
        self.controls.toggleLauncher_(None)
        event = S(window=lambda: self.native, keyCode=lambda: 53)
        self.assertIs(self.controls.local_event(event), event)
        self.controls.javascript.assert_not_called()

    def test_hover_opens_then_dismisses_after_leave_grace(self):
        self.poll(0)
        self.poll(0.21)
        self.assertTrue(self.controls.expanded)
        self.native.orderFrontRegardless.assert_called_once()
        self.mouse.x, self.mouse.y = 20, 50
        self.poll(0.3)
        self.poll(0.81)
        self.assertFalse(self.controls.expanded)

    def test_explicit_hide_requires_leaving_hotspot_before_hover_can_reopen(self):
        self.controls.expanded = True
        self.controls.hide()
        self.poll(0)
        self.poll(1)
        self.assertFalse(self.controls.expanded)
        self.mouse.x = 20
        self.poll(2)
        self.mouse.x = 756
        self.poll(3)
        self.poll(3.21)
        self.assertTrue(self.controls.expanded)

    def test_click_pins_open_launcher_and_escape_closes_intake(self):
        self.controls.expanded = True
        click = S(window=lambda: self.native, type=lambda: 1)
        self.controls.local_event(click)
        self.assertTrue(self.controls.pinned)
        self.mouse.x, self.mouse.y = 20, 50
        self.poll(0)
        self.poll(10)
        self.assertTrue(self.controls.expanded)
        self.controls.view = "intake"
        escape = S(window=lambda: self.native, type=lambda: 10, keyCode=lambda: 53)
        self.assertIsNone(self.controls.local_event(escape))
        self.assertFalse(self.controls.expanded)

    def test_analysis_is_not_closed_by_escape_or_hover(self):
        self.controls.view = "proc"
        self.controls.expanded = True
        self.mouse.x, self.mouse.y = 20, 50
        self.poll(0)
        self.poll(10)
        event = S(window=lambda: self.native, type=lambda: 10, keyCode=lambda: 53)
        self.assertIs(self.controls.local_event(event), event)
        self.assertTrue(self.controls.expanded)

    def test_shortcut_conflict_is_reported_in_menu(self):
        self.controls.hotkey = None
        self.controls.update_menu()
        self.assertIn("shortcut unavailable", self.controls.toggle_item.setTitle_.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
