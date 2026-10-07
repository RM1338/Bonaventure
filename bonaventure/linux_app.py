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
        except context.HistoryParseError:
            return dict(ok=False, name=name, error="This document could not be read.")
        has_text = any(p.strip() for p in pages)
        entry = dict(id=uuid.uuid4().hex[:8], path=str(path), name=name)
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
        self._scan, self._histories = None, []
        self._current = case_id
        _hypr_rules()
        if self._review is None:
            self._review = _review_window(self, case_id)
        else:
            self._review.load_url(str(UI / "review.html"))
            self._review.set_title(REVIEW_TITLE.format(case_id))
            self._review.show()

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
    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "bonaventure.sock"


def _serve_toggle(api):
    """Single-instance control: `scripts/bonaventure-toggle` (bar button / keybind) writes 'toggle' here."""
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


def _review_window(api, case_id):
    w = webview.create_window(REVIEW_TITLE.format(case_id), str(UI / "review.html"), js_api=api, width=1600, height=960,
                              min_size=(1200, 720), background_color="#000000", frameless=True, easy_drag=False)
    w.events.closed += api._on_review_closed
    return w


def _already_running():
    """Single instance: two copies would each load ~5 GB of models onto a 6 GB GPU. Hand over to the running one."""
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
    api._launcher = webview.create_window(ISLAND_TITLE, str(UI / "island_linux.html"), js_api=api, width=340, height=40,
                                          frameless=True, easy_drag=False, resizable=True, background_color="#000000", min_size=(100, 24))
    if reopen:
        if not (pipeline.CASES / reopen / "result.json").exists():
            sys.exit(f"No saved case {reopen} in {pipeline.CASES}")
        api._current = reopen
        api._review = _review_window(api, reopen)
    threading.Thread(target=_serve_toggle, args=(api,), daemon=True).start()
    if os.environ.get("BV_START") == "expand":
        api._launcher.events.loaded += lambda: threading.Timer(0.6, api._launcher.evaluate_js, ["expand()"]).start()
    if os.environ.get("BV_DEBUG_JS"):  # dev hook: drive the island for screenshots, e.g. BV_DEBUG_JS="expand()"
        api._launcher.events.loaded += lambda: threading.Timer(1.0, api._launcher.evaluate_js, [os.environ["BV_DEBUG_JS"]]).start()
    webview.start(debug=bool(os.environ.get("BV_DEBUG")))


if __name__ == "__main__":
    main()
