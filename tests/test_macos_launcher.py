"""Check notch clearance and animation choices without requiring AppKit."""
import sys
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch

from bonaventure.macos_launcher import _place


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

    def screen(self):
        return self.display

    def isVisible(self):
        return self.visible

    def setFrame_display_(self, rect, display):
        self.rect = rect
        self.animated = False

    def setFrame_display_animate_(self, rect, display, animate):
        self.rect = rect
        self.animated = animate


class PlacementTests(unittest.TestCase):
    def place(self, native, width, height, *, animate=False, reduced_motion=False):
        appkit = S(NSMakeRect=lambda *rect: rect, NSWorkspace=S(sharedWorkspace=lambda: S(
            accessibilityDisplayShouldReduceMotion=lambda: reduced_motion)))
        with patch.dict(sys.modules, {"AppKit": appkit}):
            _place(native, width, height, 8, animate)

    def test_expansion_preserves_top_and_camera_clearance(self):
        native = Native(Screen())
        self.place(native, 340, 40)
        self.assertEqual(native.rect, (586, 910, 340, 72))
        self.place(native, 660, 240, animate=True)
        self.assertEqual(native.rect, (426, 710, 660, 272))
        self.assertTrue(native.animated)

    def test_external_display_respects_origin_and_menu_bar(self):
        native = Native(Screen(x=-1920, y=100, width=1920, height=1080, menu=24, safe=0))
        self.place(native, 340, 40)
        self.assertEqual(native.rect, (-1130, 1108, 340, 40))

    def test_reduce_motion_disables_window_animation(self):
        native = Native(Screen())
        self.place(native, 660, 240, animate=True, reduced_motion=True)
        self.assertFalse(native.animated)

    def test_hidden_launcher_resizes_without_animation(self):
        native = Native(Screen(), visible=False)
        self.place(native, 340, 40, animate=True)
        self.assertFalse(native.animated)


if __name__ == "__main__":
    unittest.main()
