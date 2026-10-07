"""Windows shell: centered launcher and Ctrl+Alt+B hotkey, sharing desktop.Api."""
import os
import sys
import threading

import webview

from . import pipeline
from .desktop import Api, ISLAND_TITLE, UI, _review_window


class WindowsApi(Api):
    def __init__(self):
        super().__init__()
        self._launcher_visible = True
        self._launcher_screen = None

    def _place_island(self, w, h, view):
        self._launcher.resize(w, h)
        if self._launcher_screen:
            screen = self._launcher_screen
            self._launcher.move(screen.x + (screen.width - w) // 2,
                                screen.y + (screen.height - h) // 2)

    def on_shortcut(self):
        if self._launcher_visible:
            self._launcher.hide()
        else:
            self._launcher.show()
            self._launcher.evaluate_js("window.expand && expand()")
        self._launcher_visible = not self._launcher_visible

    def _focus_island(self):
        self._launcher.show()
        self._launcher_visible = True

    def window_zoom(self):
        if self._review:
            self._review.toggle_fullscreen()


def _serve_windows_hotkey(api):
    """Ctrl+Alt+B shows or hides the launcher from any Windows application."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hotkey_id = 1
    modifiers = 0x0001 | 0x0002 | 0x4000  # Alt, Ctrl, no key repeat
    if not user32.RegisterHotKey(None, hotkey_id, modifiers, ord("B")):
        print("[hotkey] Ctrl+Alt+B is unavailable (already in use).", flush=True)
        return
    try:
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == 0x0312 and message.wParam == hotkey_id:
                api.on_shortcut()
    finally:
        user32.UnregisterHotKey(None, hotkey_id)


def main():
    if sys.platform != "win32":
        raise SystemExit("The Windows desktop requires Windows; launch bonaventure.app for this OS.")
    api = WindowsApi()
    api._launcher_screen = webview.screens[0]
    screen = api._launcher_screen
    api._launcher = webview.create_window(
        ISLAND_TITLE, str(UI / "island.html"), js_api=api, width=340, height=40,
        x=screen.x + (screen.width - 340) // 2, y=screen.y + (screen.height - 40) // 2,
        screen=screen, frameless=True, easy_drag=False, resizable=True,
        background_color="#000000", min_size=(100, 24))
    reopen = sys.argv[1] if len(sys.argv) > 1 else None
    if reopen:
        if not (pipeline.CASES / reopen / "result.json").exists():
            sys.exit(f"No saved case {reopen} in {pipeline.CASES}")
        api._current = reopen
        api._review = _review_window(api, reopen)
    threading.Thread(target=_serve_windows_hotkey, args=(api,), daemon=True).start()
    if os.environ.get("BV_START") == "expand":
        api._launcher.events.loaded += lambda: threading.Timer(0.6, api._launcher.evaluate_js, ["expand()"]).start()
    if os.environ.get("BV_DEBUG_JS"):
        api._launcher.events.loaded += lambda: threading.Timer(1.0, api._launcher.evaluate_js, [os.environ["BV_DEBUG_JS"]]).start()
    webview.start(debug=bool(os.environ.get("BV_DEBUG")))


if __name__ == "__main__":
    main()
