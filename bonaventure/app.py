"""Bonaventure desktop client: floating quick launcher + full evidence-review window (pywebview, native windows)."""
import base64
import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

import webview

from . import context, imaging, pipeline, report

UI = Path(__file__).resolve().parent / "ui"
STAGE = pipeline.CASES / "_staging"
SCAN_TYPES = (".png", ".jpg", ".jpeg", ".dcm", ".dicom", ".bmp", ".tif", ".tiff", ".webp")
HISTORY_TYPES = (".pdf", ".txt", ".md")


ISLAND_TITLE = "Bonaventure"
REVIEW_TITLE = "Bonaventure — {}"
ISLAND_TOP = 8


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


def _data_url(path, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


class Api:
    """Everything here is callable from the UI as window.pywebview.api.<name>(...)."""

    def __init__(self):
        self._engine = imaging.ImagingEngine()
        self._cases = {}
        self._scan = None
        self._histories = []
        self._launcher = None
        self._launcher_visible = True
        self._launcher_screen = None
        self._review = None

    # ----- island geometry -----
    def island(self, w, h):
        """Resize the island and keep it centred at the top of the focused monitor (Hyprland animates the change)."""
        w, h = int(w), int(h)
        if _on_hyprland():
            _hypr_rules()
            mx, my, mw, scale = _focused_monitor()
            w, h = round(w / scale), round(h / scale)  # WebKitGTK lays out in device pixels; Hyprland sizes in logical ones
            sel = f'window = "title:^{ISLAND_TITLE}$"'
            _hypr(f"hl.dsp.window.resize({{ x = {w}, y = {h}, {sel} }})")
            _hypr(f"hl.dsp.window.move({{ x = {int(mx + (mw - w) / 2)}, y = {my + ISLAND_TOP}, {sel} }})")
        else:
            self._launcher.resize(w, h)
            if os.name == "nt" and self._launcher_screen:
                screen = self._launcher_screen
                self._launcher.move(screen.x + (screen.width - w) // 2,
                                    screen.y + (screen.height - h) // 2)

    def toggle_launcher(self):
        """Show or hide the launcher from the Windows global shortcut."""
        if self._launcher_visible:
            self._launcher.hide()
        else:
            self._launcher.show()
            self._launcher.evaluate_js("window.expand && expand()")
        self._launcher_visible = not self._launcher_visible

    # ----- review window controls (traffic lights) -----
    def window_close(self):
        if self._review:
            self._review.destroy()

    def window_zoom(self):
        # always address the review window explicitly: a focus-based dispatch could hit whatever window has focus
        _hypr('hl.dsp.window.fullscreen({ mode = "maximized", window = "title:^Bonaventure — " })')

    # ----- status -----
    def engine_status(self):
        return self._engine.status

    def drop_uris(self, uris):
        """file:// links from a drag (Wayland file managers send these instead of File objects) -> staged inputs."""
        import time as _time
        from urllib.parse import unquote, urlparse
        staged, now = [], _time.monotonic()
        recent = getattr(self, "_recent_drops", {})
        for u in uris:
            path = str(Path(unquote(urlparse(u).path) if u.startswith("file://") else u).resolve())
            # GTK delivers each dropped file twice (plain path, then file:// URI): ignore a repeat within 2 s
            if not Path(path).is_file() or now - recent.get(path, -10) < 2:
                continue
            recent[path] = now
            if Path(path).suffix.lower() in HISTORY_TYPES and any(h.get("source") == path for h in self._histories):
                continue  # already attached
            if Path(path).suffix.lower() in HISTORY_TYPES:
                staged.append(dict(kind="history", items=[self._stage_history(path)]))
            else:
                staged.append(dict(kind="scan", items=[self._stage_scan(path)]))
        self._recent_drops = recent
        return staged

    # ----- intake -----
    def pick_scan(self):
        paths = self._dialog(False, "Chest radiographs (*.png;*.jpg;*.jpeg;*.dcm;*.dicom;*.bmp;*.tif;*.tiff;*.webp)")
        return self._stage_scan(paths[0]) if paths else None

    def pick_history(self):
        paths = self._dialog(True, "Clinical documents (*.pdf;*.txt;*.md)")
        return [self._stage_history(p) for p in paths or []]

    def drop_file(self, kind, name, b64):
        STAGE.mkdir(parents=True, exist_ok=True)
        path = STAGE / f"{uuid.uuid4().hex[:8]}_{Path(name).name}"
        path.write_bytes(base64.b64decode(b64.split(",", 1)[-1]))
        if kind == "scan":
            return self._stage_scan(path, name)
        return [self._stage_history(path, name)]

    def remove_history(self, file_id):
        self._histories = [h for h in self._histories if h["id"] != file_id]

    def clear_scan(self):
        self._scan = None

    def clear_intake(self):
        self._scan, self._histories = None, []

    def _dialog(self, multiple, filt):
        kind = getattr(webview, "FileDialog", None)
        mode = kind.OPEN if kind else webview.OPEN_DIALOG
        return self._launcher.create_file_dialog(mode, allow_multiple=multiple, file_types=(filt, "All files (*.*)"))

    def _stage_scan(self, path, name=None):
        path, name = Path(path), name or Path(path).name
        if path.suffix.lower() not in SCAN_TYPES:
            return dict(ok=False, name=name, error="Unsupported file type. Use PNG, JPEG or DICOM.")
        try:
            img, meta = imaging.load_scan(path)
        except imaging.InvalidScan:
            return dict(ok=False, name=name, error="This file could not be read as an image.")
        q = imaging.check_quality(img, meta)
        thumb = STAGE / f"thumb_{uuid.uuid4().hex[:8]}.png"
        STAGE.mkdir(parents=True, exist_ok=True)
        img.thumbnail((160, 160))
        img.save(thumb)
        self._scan = dict(path=str(path), name=name)
        return dict(ok=True, name=name, view=meta["view"], dims=f"{meta['width']} × {meta['height']}",
                    size=_size(path), quality=q["state"], warnings=q["warnings"], thumb=_data_url(thumb))

    def _stage_history(self, path, name=None):
        path, name = Path(path), name or Path(path).name
        if path.suffix.lower() not in HISTORY_TYPES:
            return dict(ok=False, name=name, error="Unsupported document. Use PDF or text.")
        try:
            pages = context.read_pages(path)
        except context.HistoryParseError as e:
            return dict(ok=False, name=name, error=str(e))
        has_text = any(p.strip() for p in pages)
        entry = dict(id=uuid.uuid4().hex[:8], path=str(path), name=name, source=str(Path(path).resolve()))
        self._histories.append(entry)
        return dict(ok=True, id=entry["id"], name=name, pages=len(pages), kind=path.suffix[1:].upper(), size=_size(path),
                    doc_type=context.doc_type("\n".join(pages), name) if has_text else None, has_text=has_text)

    # ----- analysis -----
    def analyze(self, symptoms_text):
        if not self._scan:
            return dict(error="Add a chest X-ray to start.")
        case = pipeline.Case(self._scan, self._histories, symptoms_text or "")
        self._cases[case.id] = case
        threading.Thread(target=case.run, args=(self._engine,), daemon=True).start()
        return dict(case_id=case.id)

    def progress(self, case_id):
        return self._cases[case_id].progress()

    def open_review(self, case_id):
        self._current = case_id
        _hypr_rules()
        if self._review is None:
            self._review = _review_window(self, case_id)
        else:
            # WebView2 may skip navigation to the same URL. Give each case a
            # distinct URL so scripts and the image are loaded for the new result.
            review_url = self._review.real_url.split("?", 1)[0]
            self._review.load_url(f"{review_url}?case={case_id}")
            self._review.set_title(REVIEW_TITLE.format(case_id))
            self._review.show()
        self._scan, self._histories = None, []

    def _on_review_closed(self):
        self._review = None
        self._launcher.evaluate_js("window.resetLauncher && resetLauncher()")

    def current_case(self):
        return self._current

    def get_case(self, case_id):
        case = self._cases.get(case_id)
        result = case.result if case else json.loads((pipeline.CASES / case_id / "result.json").read_text())
        return dict(result, image=_data_url(pipeline.CASES / case_id / "scan.png"))

    def new_case(self):
        self._launcher.evaluate_js("window.resetLauncher && (resetLauncher(), expand())")
        _hypr(f'hl.dsp.focus({{ window = "title:^{ISLAND_TITLE}$" }})')

    # ----- dictation (offline Whisper) -----
    def start_dictation(self):
        if not hasattr(self, "_dictation"):
            from .dictation import Dictation
            self._dictation = Dictation()
        if not self._dictation.available():
            return dict(error="Speech model not installed (see README).")
        self._dictation.start()
        return dict(ok=True)

    def dictation_partial(self):
        return self._dictation.partial() if hasattr(self, "_dictation") else dict(text="", recording=False, seconds=0)

    def stop_dictation(self):
        try:
            return dict(text=self._dictation.stop())
        except Exception as e:
            return dict(error=f"Could not transcribe: {e}")

    # ----- clinician challenges a finding -----
    def challenge(self, case_id, finding_id, verdict, note):
        from PIL import Image
        from . import reconcile
        result = self.get_case(case_id)
        f = next(x for x in result["findings"] if x["id"] == finding_id)
        second = None
        mg = self._engine.models.get("reasoning") if not self._engine.mock else None
        if mg:
            with self._engine._lock:
                second = mg.second_look(Image.open(pipeline.CASES / case_id / "scan.png"), f["canonical_name"], verdict, note)
        d = reconcile.discuss(f, verdict, result["quality"], second)
        d.update(note=note, finding=f["display_name"], bonaventure_status=f["status"])
        return d

    def record_override(self, case_id, finding_id, verdict, note, discussion):
        """The clinician's verdict is final: store it with the case (and the report) next to what Bonaventure said."""
        from datetime import datetime
        path = pipeline.CASES / case_id / "result.json"
        result = json.loads(path.read_text())
        result.setdefault("overrides", {})[finding_id] = dict(verdict=verdict, note=note, at=datetime.now().isoformat(timespec="seconds"),
                                                             discussion=discussion)
        path.write_text(json.dumps(result, indent=2))
        if case_id in self._cases and self._cases[case_id].result:
            self._cases[case_id].result["overrides"] = result["overrides"]
        return result["overrides"]

    # ----- outputs -----
    def export_report(self, case_id):
        try:
            path = report.generate(self.get_case(case_id))
        except Exception as e:
            return dict(error="The evidence report could not be generated.", details=repr(e))
        _open(path)
        return dict(path=str(path.relative_to(pipeline.ROOT)))

    def open_source(self, path):
        if Path(path).exists():
            _open(path)

    def quit(self):
        for w in list(webview.windows):
            w.destroy()


def _size(path):
    n = Path(path).stat().st_size
    return f"{n / 1e6:.1f} MB" if n > 1e5 else f"{n / 1e3:.0f} KB"


def _open(path):
    if os.name == "nt":
        os.startfile(str(Path(path).resolve()))
        return
    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "bonaventure.sock"


def _serve_toggle(api):
    """Single-instance control: `scripts/bonaventure-toggle` (bar button / keybind) writes 'toggle' here."""
    if os.name == "nt":
        return
    import socket
    SOCKET.unlink(missing_ok=True)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCKET))
    srv.listen(2)
    while True:
        conn, _ = srv.accept()
        with conn:
            if conn.recv(64).strip() == b"toggle":
                api._launcher.evaluate_js("window.toggleIsland && toggleIsland()")
                _hypr(f'hl.dsp.focus({{ window = "title:^{ISLAND_TITLE}$" }})')


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
                api.toggle_launcher()
    finally:
        user32.UnregisterHotKey(None, hotkey_id)


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


def _deliver(api, uris):
    staged = api.drop_uris(uris)
    if staged:
        api._launcher.evaluate_js(f"window.onFilesStaged && onFilesStaged({json.dumps(staged)})")


def _review_window(api, case_id):
    width, height, position = 1600, 960, {}
    if os.name == "nt":
        screen = api._launcher_screen or webview.screens[0]
        area = screen.frame
        left, top = (area.X, area.Y) if area else (screen.x, screen.y)
        available_w, available_h = (area.Width, area.Height) if area else (screen.width, screen.height)
        width, height = min(width, available_w - 32), min(height, available_h - 32)
        position = dict(x=left + (available_w - width) // 2,
                        y=top + (available_h - height) // 2, screen=screen)
    w = webview.create_window(REVIEW_TITLE.format(case_id), str(UI / "review.html"), js_api=api, width=width, height=height,
                              min_size=(min(1200, width), min(720, height)), background_color="#000000", frameless=True,
                              easy_drag=False, **position)
    w.events.closed += api._on_review_closed
    return w


def _already_running():
    """Single instance: two copies would each load ~5 GB of models onto a 6 GB GPU. Hand over to the running one."""
    if os.name == "nt":
        return False
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
            c.settimeout(1)
            c.connect(str(SOCKET))
            c.sendall(b"toggle")
        return True
    except OSError:
        return False


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
    api = Api()
    reopen = sys.argv[1] if len(sys.argv) > 1 else None  # e.g. `./run.sh BV-002` reopens a saved case
    window_position = {}
    if os.name == "nt":
        api._launcher_screen = webview.screens[0]
        screen = api._launcher_screen
        window_position = dict(x=screen.x + (screen.width - 340) // 2,
                               y=screen.y + (screen.height - 40) // 2, screen=screen)
    api._launcher = webview.create_window(ISLAND_TITLE, str(UI / "island.html"), js_api=api, width=340, height=40,
                                          frameless=True, easy_drag=False, resizable=True, background_color="#000000", min_size=(100, 24),
                                          **window_position)
    if reopen:
        if not (pipeline.CASES / reopen / "result.json").exists():
            sys.exit(f"No saved case {reopen} in {pipeline.CASES}")
        api._current = reopen
        api._review = _review_window(api, reopen)
    threading.Thread(target=_serve_toggle, args=(api,), daemon=True).start()
    if os.name == "nt":
        threading.Thread(target=_serve_windows_hotkey, args=(api,), daemon=True).start()
    if sys.platform.startswith("linux"):
        api._launcher.events.loaded += lambda: _bind_file_drops(api)
    if os.environ.get("BV_START") == "expand":
        api._launcher.events.loaded += lambda: threading.Timer(0.6, api._launcher.evaluate_js, ["expand()"]).start()
    if os.environ.get("BV_DEBUG_JS"):  # dev hook: drive the island for screenshots, e.g. BV_DEBUG_JS="expand()"
        api._launcher.events.loaded += lambda: threading.Timer(1.0, api._launcher.evaluate_js, [os.environ["BV_DEBUG_JS"]]).start()
    webview.start(debug=bool(os.environ.get("BV_DEBUG")))


if __name__ == "__main__":
    main()
