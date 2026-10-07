"""Menu bar entry and notch hover activation. Imported only on macOS."""
import os
import threading
import time

import AppKit
import objc
from Foundation import NSRunLoop, NSRunLoopCommonModes, NSTimer
from PyObjCTools import AppHelper

from .launcher_hover import HoverIntent
from .macos_launcher import _notch_layout
from .macos_hotkey import GlobalHotKey
from queue import Queue


class MenuBarController(AppKit.NSObject):
    @objc.python_method
    def start(self, api):
        self.api = api
        self.intent = HoverIntent()
        self.pinned = os.environ.get("BV_START") == "expand"
        self.suppressed = False
        self.view = "idle"
        self.expanded = self.pinned
        self.tracking_inside = False
        self.commands = Queue()
        threading.Thread(target=self.command_worker, daemon=True).start()
        self.stopped = False
        self.file_dialog_open = False
        self.file_picker = None
        self.item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        button = self.item.button()
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_("waveform.path.ecg", "Bonaventure")
        if image:
            image.setTemplate_(True)
            image.setSize_(AppKit.NSMakeSize(18, 18))
            button.setImage_(image)
        else:
            button.setTitle_("B")
        button.setToolTip_("Bonaventure")
        menu = AppKit.NSMenu.alloc().init()
        self.toggle_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Open launcher", "toggleLauncher:", "")
        self.toggle_item.setTarget_(self)
        menu.addItem_(self.toggle_item)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit Bonaventure", "quitApp:", "")
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)
        self.item.setMenu_(menu)
        self.monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            AppKit.NSEventMaskLeftMouseDown | AppKit.NSEventMaskKeyDown, self.local_event
        )
        self.timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(0.05, self, "pollHover:", None, True)
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, NSRunLoopCommonModes)
        native = api._launcher.native
        self.tracking = AppKit.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            AppKit.NSZeroRect, AppKit.NSTrackingMouseEnteredAndExited | AppKit.NSTrackingActiveAlways | AppKit.NSTrackingInVisibleRect,
            self, None)
        native.contentView().addTrackingArea_(self.tracking)
        self.mouse_monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            AppKit.NSEventMaskMouseMoved | AppKit.NSEventMaskLeftMouseDragged, self.global_mouse)
        self.hotkey = None
        try:
            self.hotkey = GlobalHotKey(lambda: AppHelper.callAfter(self.toggleLauncher_, None))
            print("[launcher] Global Option-Command-B shortcut registered")
        except Exception as error:
            print(f"[launcher] {error}")
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        self.update_menu()

    @objc.python_method
    def command_worker(self):
        while True:
            code = self.commands.get()
            if code is None:
                return
            try:
                self.api._launcher.evaluate_js(code)
            except Exception as error:
                if not self.stopped:
                    print(f"[launcher] {error}")

    @objc.python_method
    def javascript(self, code):
        self.commands.put(code)

    @objc.python_method
    def update_menu(self):
        label = "Hide launcher" if self.expanded else "Open launcher"
        self.toggle_item.setTitle_(label + ("  ⌥⌘B" if self.hotkey else " (shortcut unavailable)"))

    @objc.python_method
    def reveal(self, pinned=False):
        if self.file_dialog_open:
            return
        self.pinned = pinned
        self.expanded = True
        native = self.api._launcher.native
        if pinned:
            native.makeKeyAndOrderFront_(None)
        else:
            native.orderFrontRegardless()
        self.javascript("window.revealIsland && revealIsland()")
        self.update_menu()

    @objc.python_method
    def hide(self):
        if self.file_dialog_open:
            return
        self.pinned = False
        self.expanded = False
        self.suppressed = True
        self.intent = HoverIntent()
        # Release focus after the shell has finished closing, rather than
        # triggering a menu-bar focus repaint in the middle of its animation.
        self.javascript("window.dismissIsland && dismissIsland()")
        self.update_menu()

    def toggleLauncher_(self, sender):
        if not self.api._launcher_ready:
            return
        if self.expanded:
            self.hide()
        else:
            self.reveal(pinned=True)

    def quitApp_(self, sender):
        threading.Thread(target=self.api.quit, daemon=True).start()

    @objc.python_method
    def local_event(self, event):
        if self.file_dialog_open:
            return event
        if event.window() == self.api._launcher.native:
            if event.type() == AppKit.NSEventTypeLeftMouseDown:
                self.pinned = True
                if not self.expanded:
                    self.reveal(pinned=True)
            elif event.keyCode() == 53:  # Explicit Escape hides the panel without canceling analysis
                self.hide()
                return None
            else:
                self.pinned = True
        return event

    def mouseEntered_(self, event):
        self.tracking_inside = True
        self.pollHover_(None)

    def mouseExited_(self, event):
        self.tracking_inside = False
        self.pollHover_(None)

    @objc.python_method
    def global_mouse(self, event):
        self.pollHover_(None)

    def pollHover_(self, timer):
        if self.stopped or self.file_dialog_open or not self.api._launcher_ready:
            return
        native = self.api._launcher.native
        mouse = AppKit.NSEvent.mouseLocation()
        hotspot = False
        for screen in AppKit.NSScreen.screens():
            layout, frame, visible = _notch_layout(screen), screen.frame(), screen.visibleFrame()
            top = frame.origin.y + frame.size.height if layout["notched"] else visible.origin.y + visible.size.height
            width = layout["hit_width"]
            x = layout["center_x"] - width / 2
            if x <= mouse.x <= x + width and top - layout["top_inset"] - 28 <= mouse.y <= top:
                hotspot = True
                if not self.expanded:
                    native._bv_screen = screen
                break
        if self.suppressed:
            if hotspot:
                return
            self.suppressed = False
        rect = native.frame()
        inside = (rect.origin.x - 8 <= mouse.x <= rect.origin.x + rect.size.width + 8
                  and rect.origin.y - 8 <= mouse.y <= rect.origin.y + rect.size.height + 8)
        action = self.intent.update(time.monotonic(), hotspot=hotspot, inside=inside,
                                    visible=self.expanded, pinned=self.pinned, processing=self.view == "proc")
        if action == "open":
            if os.environ.get("BV_DEBUG"):
                print("[launcher] Hover reveal")
            self.reveal()
        elif action == "close":
            self.hide()

    @objc.python_method
    def stop(self):
        def cleanup():
            if self.stopped:
                return
            self.stopped = True
            if self.file_picker is not None:
                self.file_picker.cancel_(None)
            self.timer.invalidate()
            AppKit.NSEvent.removeMonitor_(self.monitor)
            if self.mouse_monitor:
                AppKit.NSEvent.removeMonitor_(self.mouse_monitor)
            self.api._launcher.native.contentView().removeTrackingArea_(self.tracking)
            if self.hotkey:
                self.hotkey.close()
            self.commands.put(None)
            AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
        AppHelper.callAfter(cleanup)


def install_controls(api):
    def install():
        if api._mac_controls is None:
            controller = MenuBarController.alloc().init()
            api._mac_controls = controller
            controller.start(api)
    AppHelper.callAfter(install)
