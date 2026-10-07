"""macOS desktop shell: notch-joined island, menu-bar controls and the global hotkey (AppKit via PyObjC).
All application logic lives in desktop.Api and is shared with Linux; this file only places windows and wires macOS controls."""
import os
import sys
import threading

import webview

from . import pipeline
from .desktop import Api, HISTORY_TYPES, SCAN_TYPES, ISLAND_TITLE, ISLAND_TOP, UI, _already_running, _review_window, _serve_toggle


class MacApi(Api):
    def __init__(self):
        super().__init__()
        self._launcher_ready = False
        self._mac_controls = None

    def launcher_layout(self):
        from .macos_launcher import launcher_layout
        return launcher_layout(self._launcher)

    def dismiss_launcher(self):
        if self._mac_controls is not None:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self._mac_controls.hide)

    def _dialog(self, multiple, filt):
        if self._mac_controls is None:
            return super()._dialog(multiple, filt)
        from .macos_files import choose_files
        extensions = HISTORY_TYPES if multiple else SCAN_TYPES
        return choose_files(self, multiple, [ext.lstrip(".") for ext in extensions])

    def _place_island(self, w, h, view):
        """Resize the island, keeping it centred and joined to the Mac's notch."""
        from PyObjCTools import AppHelper
        from .macos_launcher import resize_launcher
        if self._mac_controls is not None and view is not None:
            AppHelper.callAfter(setattr, self._mac_controls, "view", view)
            AppHelper.callAfter(setattr, self._mac_controls, "expanded", view != "idle")
            AppHelper.callAfter(self._mac_controls.update_menu)
        resize_launcher(self._launcher, w, h, ISLAND_TOP, view)
        self._launcher_ready = True

    def on_shortcut(self):
        if self._mac_controls is not None:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self._mac_controls.toggleLauncher_, None)
        else:
            super().on_shortcut()

    def quit(self):
        if self._mac_controls is not None:
            self._mac_controls.stop()
        super().quit()


def main():
    if _already_running():
        print("Bonaventure is already running — toggled its island.")
        return
    api = MacApi()
    reopen = sys.argv[1] if len(sys.argv) > 1 else None  # e.g. `./run.sh BV-002` reopens a saved case
    api._launcher = webview.create_window(ISLAND_TITLE, str(UI / "island_macos.html"), js_api=api, width=340, height=40,
                                          frameless=True, easy_drag=False, resizable=True, background_color="#000000",
                                          transparent=True, min_size=(100, 24))
    from .macos_controls import install_controls
    from .macos_launcher import configure_launcher

    def setup_launcher():
        configure_launcher(api._launcher, ISLAND_TOP)
        install_controls(api)
    api._launcher.events.shown += setup_launcher
    api._launcher.events.closed += lambda: api._mac_controls and api._mac_controls.stop()
    if reopen:
        if not (pipeline.CASES / reopen / "result.json").exists():
            sys.exit(f"No saved case {reopen} in {pipeline.CASES}")
        api._current = reopen
        api._review = _review_window(api, reopen)
    threading.Thread(target=_serve_toggle, args=(api,), daemon=True).start()
    if os.environ.get("BV_DEBUG_JS"):  # dev hook: drive the island for screenshots, e.g. BV_DEBUG_JS="expand()"
        api._launcher.events.loaded += lambda: threading.Timer(1.0, api._launcher.evaluate_js, [os.environ["BV_DEBUG_JS"]]).start()
    webview.start(debug=bool(os.environ.get("BV_DEBUG")))


if __name__ == "__main__":
    main()
