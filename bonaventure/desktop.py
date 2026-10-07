"""Platform-neutral desktop core: the Api the island and review UIs call (intake, analysis, review, challenge, dictation,
reports). linux_app.py and macos_app.py subclass it and only implement window placement / shortcuts for their OS."""
import base64
import json
import os
import shutil
import subprocess
import sys
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











def _data_url(path, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


class Api:
    """Everything here is callable from the UI as window.pywebview.api.<name>(...)."""

    def __init__(self):
        self._dictation_lock = threading.RLock()
        self._engine = imaging.ImagingEngine()
        self._cases = {}
        self._scan = None
        self._histories = []
        self._launcher = None
        self._review = None

    # ----- island geometry -----
    def island(self, w, h, view=None):
        """Resize the island (the UI measures its content and asks). Placement is platform-specific."""
        self._place_island(int(w), int(h), view)

    # ----- platform hooks (linux_app / macos_app override these) -----
    def _place_island(self, w, h, view):
        self._launcher.resize(w, h)

    def _before_review(self):
        pass

    def _focus_island(self):
        pass

    def on_shortcut(self):
        """The global shortcut / menu-bar item was used: show or hide the island."""
        self._launcher.evaluate_js("window.toggleIsland && toggleIsland()")
        self._focus_island()

    # ----- review window controls (traffic lights) -----
    def window_close(self):
        if self._review:
            self._review.destroy()

    def window_zoom(self):
        """Green traffic light: maximise the review window (platform-specific; no-op by default)."""

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
        self._before_review()
        if self._review is None:
            self._review = _review_window(self, case_id)
        else:
            # WebView2 can skip navigation to the same URL. Force a fresh case load.
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
        self._focus_island()

    # ----- dictation (offline Whisper) -----
    def start_dictation(self):
        with self._dictation_lock:
            try:
                if not hasattr(self, "_dictation"):
                    from .dictation import Dictation
                    self._dictation = Dictation()
                if not self._dictation.available():
                    return dict(error="Speech model or microphone recorder not installed (see README).")
                self._dictation.start()
                return dict(ok=True)
            except Exception as error:
                return dict(error=f"Could not start microphone: {error}")

    def dictation_partial(self):
        return self._dictation.partial() if hasattr(self, "_dictation") else dict(text="", recording=False, seconds=0)

    def stop_dictation(self):
        with self._dictation_lock:
            try:
                return dict(text=self._dictation.stop() if hasattr(self, "_dictation") else "")
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
        result = dict(path=str(path.relative_to(pipeline.ROOT)))
        try:
            _open(path)
            result["opened"] = True
        except Exception as e:
            result.update(opened=False, warning="Report saved, but could not open it in the default PDF viewer.", details=repr(e))
        return result

    def open_source(self, path):
        if Path(path).exists():
            _open(path)

    def quit(self):
        with self._dictation_lock:
            if hasattr(self, "_dictation"):
                self._dictation.stop(final=False)
        for w in list(webview.windows):
            w.destroy()


def _size(path):
    n = Path(path).stat().st_size
    return f"{n / 1e6:.1f} MB" if n > 1e5 else f"{n / 1e3:.0f} KB"


def _open(path):
    path = str(Path(path).resolve())
    if sys.platform == "win32":
        os.startfile(path)
        return
    opener = "/usr/bin/open" if sys.platform == "darwin" else shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("No default document opener found (install xdg-utils on Linux)")
    subprocess.run([opener, path], check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
                api.on_shortcut()


def _deliver(api, uris):
    staged = api.drop_uris(uris)
    if staged:
        api._launcher.evaluate_js(f"window.onFilesStaged && onFilesStaged({json.dumps(staged)})")


def _review_window(api, case_id):
    width, height, position = 1600, 960, {}
    if sys.platform == "win32":
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
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
            c.settimeout(1)
            c.connect(str(SOCKET))
            c.sendall(b"toggle")
        return True
    except OSError:
        return False




if __name__ == "__main__":
    main()
