"""Native macOS launcher positioning, joined to the camera notch.

AppKit work is queued on the main thread; pywebview API calls run on workers.
"""
from threading import Event


def _notch_layout(screen):
    inset = screen.safeAreaInsets().top if hasattr(screen, "safeAreaInsets") else 0
    width = 340
    if inset and hasattr(screen, "auxiliaryTopLeftArea"):
        left, right = screen.auxiliaryTopLeftArea(), screen.auxiliaryTopRightArea()
        width = max(width, right.origin.x - (left.origin.x + left.size.width) + 40)
    return {"notched": bool(inset), "top_inset": int(inset), "min_width": int(width)}


def launcher_layout(window):
    """Read screen metrics on AppKit's main thread for the web UI."""
    import AppKit
    from PyObjCTools import AppHelper

    ready, result = Event(), {}

    def read():
        try:
            result.update(_notch_layout(window.native.screen() or AppKit.NSScreen.mainScreen()))
        finally:
            ready.set()

    AppHelper.callAfter(read)
    if not ready.wait(5):
        raise RuntimeError("macOS screen layout did not respond")
    return result


def _place(native, width, height, gap, animate=False):
    import AppKit

    screen = native.screen() or AppKit.NSScreen.mainScreen()
    frame, visible = screen.frame(), screen.visibleFrame()
    layout = _notch_layout(screen)
    if layout["notched"]:
        # The native window includes the camera's blank area; UI controls begin
        # below it. No gap or rounded upper edge exposes the notch's outline.
        top = frame.origin.y + frame.size.height
        height += layout["top_inset"]
        width = max(width, layout["min_width"])
    else:
        top = visible.origin.y + visible.size.height - gap
    width = min(width, visible.size.width - 2 * gap)
    height = min(height, top - visible.origin.y - gap)
    x = visible.origin.x + (visible.size.width - width) / 2
    rect = AppKit.NSMakeRect(x, top - height, width, height)
    if animate and native.isVisible() and not AppKit.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion():
        native.setFrame_display_animate_(rect, True, True)
    else:
        native.setFrame_display_(rect, True)


def resize_launcher(window, width, height, gap=8):
    from PyObjCTools import AppHelper

    AppHelper.callAfter(_place, window.native, width, height, gap, True)


def configure_launcher(window, gap=8):
    import AppKit
    from PyObjCTools import AppHelper

    def configure():
        native = window.native
        native.setOpaque_(False)
        native.setBackgroundColor_(AppKit.NSColor.clearColor())
        native.setHasShadow_(False)
        # Draw the black cap over the menu bar's central notch area.
        native.setLevel_(AppKit.NSStatusWindowLevel)
        frame = native.frame()
        _place(native, frame.size.width, frame.size.height, gap)

    AppHelper.callAfter(configure)
