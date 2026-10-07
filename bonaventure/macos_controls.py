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


class MenuBarController(AppKit.NSObject):
    @objc.python_method
    def start(self, api):
        self.api = api
        self.intent = HoverIntent()
        self.pinned = os.environ.get("BV_START") == "expand"
        self.suppressed = False
        self.view = "pill"
        self.stopped = False
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
        self.toggle_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Open launcher", "toggleLauncher:", "b")
        self.toggle_item.setKeyEquivalentModifierMask_(AppKit.NSEventModifierFlagCommand | AppKit.NSEventModifierFlagOption)
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
        if not self.pinned:
            api._launcher.native.orderOut_(None)
        self.update_menu()

    @objc.python_method
    def javascript(self, code):
        # evaluate_js waits for WebKit, so never block AppKit's main thread.
        def run():
            try:
                self.api._launcher.evaluate_js(code)
            except Exception as error:
                if os.environ.get("BV_DEBUG"):
                    print(f"[launcher] {error!r}")
        threading.Thread(target=run, daemon=True).start()

    @objc.python_method
    def update_menu(self):
        self.toggle_item.setTitle_("Hide launcher" if self.api._launcher.native.isVisible() else "Open launcher")

    @objc.python_method
    def reveal(self, pinned=False):
        self.pinned = pinned
        native = self.api._launcher.native
        if pinned:
            native.makeKeyAndOrderFront_(None)
        else:
            native.orderFrontRegardless()
        self.javascript("window.revealIsland && revealIsland()")
        self.update_menu()

    @objc.python_method
    def hide(self):
        self.pinned = False
        self.suppressed = True
        self.intent = HoverIntent()
        self.api._launcher.native.orderOut_(None)
        self.javascript("window.dismissIsland && dismissIsland()")
        self.update_menu()

    def toggleLauncher_(self, sender):
        if not self.api._launcher_ready:
            return
        if self.api._launcher.native.isVisible():
            self.hide()
        else:
            self.reveal(pinned=True)

    def quitApp_(self, sender):
        threading.Thread(target=self.api.quit, daemon=True).start()

    @objc.python_method
    def local_event(self, event):
        if event.window() == self.api._launcher.native:
            if event.type() == AppKit.NSEventTypeLeftMouseDown:
                self.pinned = True
            elif event.keyCode() == 53 and self.view != "proc":  # Escape
                self.hide()
            else:
                self.pinned = True
        return event

    def pollHover_(self, timer):
        if self.stopped or not self.api._launcher_ready:
            return
        native = self.api._launcher.native
        screen = native.screen() or AppKit.NSScreen.mainScreen()
        layout, frame = _notch_layout(screen), screen.frame()
        visible_frame = screen.visibleFrame()
        top = frame.origin.y + frame.size.height - layout["top_inset"] if layout["notched"] else visible_frame.origin.y + visible_frame.size.height
        width = layout["min_width"] - 40 if layout["notched"] else 160
        x = frame.origin.x + (frame.size.width - width) / 2
        mouse = AppKit.NSEvent.mouseLocation()
        hotspot = x <= mouse.x <= x + width and top - 14 <= mouse.y <= top
        if self.suppressed:
            if hotspot:
                return
            self.suppressed = False
        rect = native.frame()
        inside = (rect.origin.x - 6 <= mouse.x <= rect.origin.x + rect.size.width + 6
                  and rect.origin.y - 6 <= mouse.y <= rect.origin.y + rect.size.height + 6)
        action = self.intent.update(time.monotonic(), hotspot=hotspot, inside=inside,
                                    visible=bool(native.isVisible()), pinned=self.pinned, processing=self.view == "proc")
        if action == "open":
            self.reveal()
        elif action == "close":
            self.hide()

    @objc.python_method
    def stop(self):
        def cleanup():
            if self.stopped:
                return
            self.stopped = True
            self.timer.invalidate()
            AppKit.NSEvent.removeMonitor_(self.monitor)
            AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
        AppHelper.callAfter(cleanup)


def install_controls(api):
    def install():
        if api._mac_controls is None:
            controller = MenuBarController.alloc().init()
            api._mac_controls = controller
            controller.start(api)
    AppHelper.callAfter(install)
