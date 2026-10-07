"""A real borderless notch panel, with a stable WebKit surface for animation."""
import os
from threading import Event


def _notch_layout(screen):
    frame, visible = screen.frame(), screen.visibleFrame()
    inset = float(screen.safeAreaInsets().top) if hasattr(screen, "safeAreaInsets") else 0
    notch_width, center = 0, frame.origin.x + frame.size.width / 2
    if hasattr(screen, "auxiliaryTopLeftArea"):
        left, right = screen.auxiliaryTopLeftArea(), screen.auxiliaryTopRightArea()
        if left.size.width and right.size.width:
            notch_width = max(0, right.origin.x - (left.origin.x + left.size.width))
            if notch_width:
                center = (left.origin.x + left.size.width + right.origin.x) / 2
                inset = max(inset, left.size.height, right.size.height)
    notched = inset > 0
    menu_height = frame.origin.y + frame.size.height - (visible.origin.y + visible.size.height)
    if notched:
        inset = max(inset, menu_height)
    notch_width = notch_width or (220 if notched else 160)
    return dict(notched=notched, top_inset=int(inset), min_width=int(max(340, notch_width + 40)),
                idle_width=int(notch_width + 8), idle_height=int(inset + 2) if notched else 10,
                hit_width=int(max(360, notch_width + 160)), center_x=center, managed=True,
                start_expanded=os.environ.get("BV_START") == "expand")


def _screen(native):
    import AppKit
    selected = getattr(native, "_bv_screen", None)
    screens = list(AppKit.NSScreen.screens())
    if selected in screens:
        return selected
    return next((s for s in screens if _notch_layout(s)["notched"]),
                native.screen() or AppKit.NSScreen.mainScreen() or screens[0])


def launcher_layout(window):
    import AppKit
    from PyObjCTools import AppHelper
    ready, result, errors = Event(), {}, []
    def read():
        try:
            result.update(_notch_layout(_screen(window.native)))
        except Exception as error:
            errors.append(error)
        finally:
            ready.set()
    AppHelper.callAfter(read)
    if not ready.wait(5):
        raise RuntimeError("macOS screen layout did not respond")
    if errors:
        raise errors[0]
    return result


def _place(native, width, height, gap, animate=False, view=None):
    import AppKit
    idle = view == "idle"
    if idle and getattr(native, "_bv_placed", False):
        # Resizing a transparent window above the menu bar damages its backing
        # surface and can flash the menu underneath. Keep the surface stable;
        # only the HTML shell contracts. Pass desktop clicks through when idle.
        native.setIgnoresMouseEvents_(True)
        if native.isKeyWindow():
            native.resignKeyWindow()
        return
    screen = _screen(native)
    frame, visible = screen.frame(), screen.visibleFrame()
    layout = _notch_layout(screen)
    top = frame.origin.y + frame.size.height if layout["notched"] else visible.origin.y + visible.size.height
    if idle:
        width, height = layout["hit_width"], layout["idle_height"] + 24
    else:
        width = max(width, layout["min_width"])
        height += layout["top_inset"]
    width = min(width, frame.size.width - 2 * gap)
    height = min(height, top - visible.origin.y - gap)
    x = layout["center_x"] - width / 2
    native.setFrame_display_(AppKit.NSMakeRect(x, top - height, width, height), True)
    native._bv_placed = True
    native.setIgnoresMouseEvents_(idle)
    # Hover activation uses global monitoring/polling even when clicks pass
    # through. Expanded placement restores input and handles display changes.


def resize_launcher(window, width, height, gap=8, view=None):
    from PyObjCTools import AppHelper
    AppHelper.callAfter(_place, window.native, width, height, gap, False, view)


def configure_launcher(window, gap=8):
    import AppKit
    from PyObjCTools import AppHelper
    from webview.platforms.cocoa import BrowserView

    class BonaventureNotchPanel(AppKit.NSPanel):
        def canBecomeKeyWindow(self):
            return True
        def canBecomeMainWindow(self):
            return False
        def constrainFrameRect_toScreen_(self, rect, screen):
            return rect

    def configure():
        original = window.native
        screen = _screen(original)
        content, delegate = original.contentView(), original.delegate()
        panel = BonaventureNotchPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            original.frame(), AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False)
        panel._bv_screen = screen
        panel.focus = True
        panel.setTitle_(window.title)
        panel.setReleasedWhenClosed_(False)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setHidesOnDeactivate_(False)
        panel.setLevel_(AppKit.NSStatusWindowLevel + 1)
        panel.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                    AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary |
                                    AppKit.NSWindowCollectionBehaviorStationary |
                                    AppKit.NSWindowCollectionBehaviorIgnoresCycle)
        panel.setAnimationBehavior_(AppKit.NSWindowAnimationBehaviorNone)
        panel.setAcceptsMouseMovedEvents_(True)
        original.setDelegate_(None)
        content.removeFromSuperview()
        original.setContentView_(AppKit.NSView.alloc().init())
        panel.setContentView_(content)
        panel.makeFirstResponder_(content)
        content.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        panel.setDelegate_(delegate)
        browser = BrowserView.instances[window.uid]
        browser.window = panel
        window.native = panel
        original.orderOut_(None)
        original.close()
        _place(panel, 340, 0, gap, view="idle")
        panel.orderFrontRegardless()
        if os.environ.get("BV_DEBUG"):
            print(f"[launcher] Screen layout: {_notch_layout(screen)}")
    AppHelper.callAfter(configure)
