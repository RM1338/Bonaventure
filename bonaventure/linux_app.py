"""Linux desktop shell (Hyprland/GTK): window placement, Hyprland rules, native drag-and-drop, single-instance toggle.
All application logic lives in desktop.py and is shared with macOS."""
import os
import sys
import threading

import webview

from . import pipeline
from .desktop import (Api, HISTORY_TYPES, ISLAND_TITLE, ISLAND_TOP, REVIEW_TITLE, SOCKET, UI, _already_running, _deliver,
                      _review_window, _serve_toggle, json, shutil, subprocess)

# ---------- Hyprland integration (no config files touched: rules live only for this Hyprland session) ----------

def _on_hyprland():
    return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")) and shutil.which("hyprctl")

def _hypr(lua):
    if _on_hyprland():
        subprocess.run(["hyprctl", "dispatch", lua], capture_output=True, timeout=3)

def _hypr_rules():
    # island: floating, pinned on every workspace, borderless pill, fully opaque, top-centre
    _hypr('(function() hl.window_rule({ match = { title = "^%s$" }, float = true, pin = true, border_size = 0, rounding = 20, '
          'opacity = "1 1", tag = "-default-opacity", no_initial_focus = false, move = { "(monitor_w/2-window_w/2)", "%d" } }) end)()'
          % (ISLAND_TITLE, ISLAND_TOP + 30))
    # GTK file pickers are transient for the pinned island, so they would open off the top edge: centre them instead
    _hypr('(function() hl.window_rule({ match = { class = "^bonaventure$", title = "^(Open|Open File|Open Files|Select File|Choose File).*$" }, '
          'float = true, center = true, size = { 900, 620 }, opacity = "1 1", tag = "-default-opacity" }) end)()')
    # review: fully opaque (diagnostic image must not show what is behind it)
    _hypr('(function() hl.window_rule({ match = { title = "^Bonaventure — .*$" }, opacity = "1 1", tag = "-default-opacity", '
          'float = true, size = { "(monitor_w-24)", "(monitor_h-48)" }, center = true }) end)()')

def _focused_monitor():
    try:
        mons = json.loads(subprocess.run(["hyprctl", "-j", "monitors"], capture_output=True, text=True, timeout=3).stdout)
        m = next((m for m in mons if m.get("focused")), mons[0])
        return m["x"], m["y"] + (m.get("reserved") or [0, 0])[1], m["width"] / m["scale"], m["scale"]  # below the bar, like a notch
    except Exception:
        return 0, 0, 1920, 1


class LinuxApi(Api):
    def _place_island(self, w, h, view):
        if _on_hyprland():
            _hypr_rules()
            mx, my, mw, scale = _focused_monitor()
            w, h = round(w / scale), round(h / scale)  # WebKitGTK lays out in device pixels; Hyprland sizes in logical ones
            sel = f'window = "title:^{ISLAND_TITLE}$"'
            _hypr(f"hl.dsp.window.resize({{ x = {w}, y = {h}, {sel} }})")
            _hypr(f"hl.dsp.window.move({{ x = {int(mx + (mw - w) / 2)}, y = {my + ISLAND_TOP}, {sel} }})")
        else:
            self._launcher.resize(w, h)

    def _before_review(self):
        _hypr_rules()

    def _focus_island(self):
        _hypr(f'hl.dsp.focus({{ window = "title:^{ISLAND_TITLE}$" }})')

    def window_zoom(self):
        # always address the review window explicitly: a focus-based dispatch could hit whatever window has focus
        _hypr('hl.dsp.window.fullscreen({ mode = "maximized", window = "title:^Bonaventure — " })')


def _bind_file_drops(api):
    """Native GTK drop handling. File managers deliver a text/uri-list; pywebview reads it with get_text(), which is empty
    for URI lists, so dropped files never arrived. Read the WebKit widget's drop with get_uris() instead."""
    from gi.repository import GLib
    from webview.platforms.gtk import BrowserView

    def on_data(_widget, _ctx, _x, _y, data, _info, _time):
        uris = list(data.get_uris() or []) or [u for u in (data.get_text() or "").splitlines() if u.strip()]
        print(f"[drop] native uris: {uris}", flush=True)
        if uris:  # stage off the GTK thread; evaluate_js from inside a GTK callback would block the main loop
            threading.Thread(target=lambda: _deliver(api, uris), daemon=True).start()
        return False

    def connect():
        view = BrowserView.instances.get(api._launcher.uid)
        if view is None:
            return True  # not created yet: try again
        view.webview.connect("drag-data-received", on_data)
        print("[drop] native handler connected", flush=True)
        return False

    GLib.timeout_add(200, connect)


def main():
    import sys
    if _already_running():
        print("Bonaventure is already running — toggled its island.")
        return
    try:  # window class "bonaventure" instead of "app.py"
        from gi.repository import GLib
        GLib.set_prgname("bonaventure")
    except ImportError:
        pass
    _hypr_rules()
    api = LinuxApi()
    reopen = sys.argv[1] if len(sys.argv) > 1 else None  # e.g. `./run.sh BV-002` reopens a saved case
    api._launcher = webview.create_window(ISLAND_TITLE, str(UI / "island.html"), js_api=api, width=340, height=40,
                                          frameless=True, easy_drag=False, resizable=True, background_color="#000000", min_size=(100, 24))
    if reopen:
        if not (pipeline.CASES / reopen / "result.json").exists():
            sys.exit(f"No saved case {reopen} in {pipeline.CASES}")
        api._current = reopen
        api._review = _review_window(api, reopen)
    threading.Thread(target=_serve_toggle, args=(api,), daemon=True).start()
    api._launcher.events.loaded += lambda: _bind_file_drops(api)
    if os.environ.get("BV_START") == "expand":
        api._launcher.events.loaded += lambda: threading.Timer(0.6, api._launcher.evaluate_js, ["expand()"]).start()
    if os.environ.get("BV_DEBUG_JS"):  # dev hook: drive the island for screenshots, e.g. BV_DEBUG_JS="expand()"
        api._launcher.events.loaded += lambda: threading.Timer(1.0, api._launcher.evaluate_js, [os.environ["BV_DEBUG_JS"]]).start()
    webview.start(debug=bool(os.environ.get("BV_DEBUG")))


if __name__ == "__main__":
    main()
