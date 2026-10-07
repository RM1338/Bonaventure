"""Check notch clearance and animation choices without requiring AppKit."""
import sys
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch

from bonaventure.macos_launcher import _place, _notch_layout


class Screen:
    def __init__(self, x=0, y=0, width=1512, height=982, menu=38, safe=32):
        self.full = S(origin=S(x=x, y=y), size=S(width=width, height=height))
        self.visible = S(origin=S(x=x, y=y), size=S(width=width, height=height-menu))
        self.safe = safe

    def frame(self):
        return self.full

    def visibleFrame(self):
        return self.visible

    def safeAreaInsets(self):
        return S(top=self.safe)


class Native:
    def __init__(self, screen, visible=True):
        self.display, self.visible = screen, visible
        self.animated = False
        self.frame_changes = 0
        self.ignores_mouse = False

    def screen(self):
        return self.display

    def isVisible(self):
        return self.visible

    def setFrame_display_(self, rect, display):
        self.frame_changes += 1
        self.rect = rect
        self.animated = False

    def setIgnoresMouseEvents_(self, ignores):
        self.ignores_mouse = ignores

    def setFrame_display_animate_(self, rect, display, animate):
        self.rect = rect
        self.animated = animate


class PlacementTests(unittest.TestCase):
    def place(self, native, width, height, *, animate=False, view=None, screens=None):
        appkit = S(NSMakeRect=lambda *rect: rect,
            NSScreen=S(screens=lambda: screens or [native.display], mainScreen=lambda: native.display))
        with patch.dict(sys.modules, {"AppKit": appkit}):
            _place(native, width, height, 8, animate, view)

    def test_expansion_preserves_top_and_camera_clearance(self):
        native = Native(Screen())
        self.place(native, 340, 40)
        self.assertEqual(native.rect, (586, 904, 340, 78))
        self.place(native, 660, 240, animate=True)
        self.assertEqual(native.rect, (426, 704, 660, 278))
        self.assertFalse(native.animated)  # Animation happens in the WebKit shell, not a reflowing window.

    def test_external_display_respects_origin_and_menu_bar(self):
        native = Native(Screen(x=-1920, y=100, width=1920, height=1080, menu=24, safe=0))
        self.place(native, 340, 40)
        self.assertEqual(native.rect, (-1130, 1116, 340, 40))

    def test_idle_keeps_invisible_hover_space_below_entire_notch(self):
        native = Native(Screen())
        self.place(native, 340, 0, view="idle")
        self.assertEqual(native.rect[1] + native.rect[3], 982)
        self.assertGreaterEqual(native.rect[3], 38 + 24)
        self.assertTrue(native.ignores_mouse)

    def test_collapse_keeps_native_surface_stable_and_passes_clicks_through(self):
        native = Native(Screen())
        self.place(native, 660, 240, view="intake")
        expanded_frame = native.rect
        self.assertFalse(native.ignores_mouse)
        self.place(native, 380, 0, view="idle")
        self.assertEqual(native.rect, expanded_frame)
        self.assertEqual(native.frame_changes, 1)
        self.assertTrue(native.ignores_mouse)
        self.place(native, 660, 240, view="intake")
        self.assertFalse(native.ignores_mouse)

    def test_repeated_idle_notifications_never_resize_native_surface(self):
        native = Native(Screen())
        self.place(native, 380, 0, view="idle")
        self.place(native, 380, 0, view="idle")
        self.assertEqual(native.frame_changes, 1)

    def test_auxiliary_screen_areas_detect_notch_when_safe_insets_are_zero(self):
        screen = Screen(safe=0)
        screen.auxiliaryTopLeftArea = lambda: S(origin=S(x=0), size=S(width=556, height=38))
        screen.auxiliaryTopRightArea = lambda: S(origin=S(x=956), size=S(width=556, height=38))
        layout = _notch_layout(screen)
        self.assertTrue(layout["notched"])
        self.assertEqual(layout["idle_width"], 408)
        self.assertEqual(layout["center_x"], 756)
        self.assertEqual(layout["top_inset"], 38)

    def test_chooses_notched_display_when_key_window_is_on_external_display(self):
        external, notched = Screen(x=-1920, width=1920, safe=0), Screen()
        native = Native(external)
        self.place(native, 340, 40, screens=[external, notched])
        self.assertEqual(native.rect, (586, 904, 340, 78))

    def test_pointer_selected_display_overrides_notched_default(self):
        external, notched = Screen(x=-1920, width=1920, safe=0), Screen()
        native = Native(notched)
        native._bv_screen = external
        self.place(native, 340, 40, screens=[external, notched])
        self.assertLess(native.rect[0], 0)
        self.assertEqual(native.rect[3], 40)


if __name__ == "__main__":
    unittest.main()
