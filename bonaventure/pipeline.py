"""Case orchestration: run each pipeline stage, track progress for the UI, capture failures, persist the result."""
import json
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

from . import context, imaging, reconcile

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"

# (step key, clinician-facing label). No model names here by design.
STEPS = [
    ("scan", "Reading chest X-ray"),
    ("history", "Extracting patient timeline"),
    ("symptoms", "Structuring current presentation"),
    ("image", "Evaluating image findings"),
    ("localize", "Localizing findings"),
    ("reconcile", "Reconciling evidence"),
    ("review", "Preparing review"),
]

ERROR_TEXT = {
    "INVALID_SCAN": ("Image analysis unavailable", "The chest X-ray could not be read.",
                     ["Unsupported image format", "Corrupt or incomplete file"]),
    "IMAGE_MODEL_FAILED": ("Image analysis unavailable", "The imaging model could not process this study.",
                           ["Unsupported image format", "Incomplete study", "Insufficient image quality"]),
    "INTERNAL": ("Analysis interrupted", "Bonaventure could not complete this case.", []),
}


def new_case_id():
    CASES.mkdir(exist_ok=True)
    nums = [int(p.name[3:]) for p in CASES.glob("BV-*") if p.name[3:].isdigit()]
    return f"BV-{max(nums, default=0) + 1:03d}"


class Case:
    def __init__(self, scan, histories, symptoms_text):
        self.id = new_case_id()
        self.dir = CASES / self.id
        (self.dir / "inputs").mkdir(parents=True)
        self.scan = Path(shutil.copy(scan["path"], self.dir / "inputs" / scan["name"]))
        self.histories = [(Path(shutil.copy(h["path"], self.dir / "inputs" / h["name"])), h["name"]) for h in histories]
        self.symptoms_text = symptoms_text.strip()
        self.steps = {k: "pending" for k, _ in STEPS}
        self.state = "PROCESSING"
        self.error = None
        self.result = None

    def progress(self):
        return dict(case_id=self.id, state=self.state, error=self.error,
                    steps=[dict(key=k, label=label, state=self.steps[k]) for k, label in STEPS])

    def _step(self, key, fn):
        self.steps[key] = "running"
        out = fn()
        self.steps[key] = "complete"
        return out

    def _fail(self, code, exc):
        title, message, causes = ERROR_TEXT[code]
        running = [k for k, s in self.steps.items() if s == "running"]
        for k in running:
            self.steps[k] = "failed"
        self.state = "FAILED"
        self.error = dict(code=code, title=title, message=message, causes=causes, details=f"{exc!r}\n\n{traceback.format_exc()}")

    def run(self, engine):
        t0 = time.time()
        try:
            try:
                img, meta = self._step("scan", lambda: imaging.load_scan(self.scan))
            except imaging.InvalidScan as e:
                return self._fail("INVALID_SCAN", e)
            quality = imaging.check_quality(img, meta)

            def parse_histories():
                events, warns = [], []
                for path, name in self.histories:
                    try:
                        ev, w = context.parse_history(path, name)
                        events += ev
                        warns += w
                    except context.HistoryParseError as e:
                        warns.append(str(e))
                return events, warns
            events, warnings = self._step("history", parse_histories)
            if not self.histories:
                self.steps["history"] = "skipped"
            symptoms = self._step("symptoms", lambda: context.parse_symptoms(self.symptoms_text))
            events += context.presentation_as_history(self.symptoms_text)

            try:
                result = self._step("image", lambda: engine.analyze(img, self.scan))
            except Exception as e:
                return self._fail("IMAGE_MODEL_FAILED", e)
            self._step("localize", lambda: None)  # localization is produced alongside the image analysis

            findings, summary = self._step("reconcile", lambda: reconcile.reconcile(result, quality, symptoms, events, bool(self.histories)))
            not_assessable = reconcile.not_assessable(symptoms, events)
            other = reconcile.other_observations(result, findings)

            def prepare():
                preview = img.copy()
                preview.thumbnail((1600, 1600))
                preview.save(self.dir / "scan.png")
                self.result = dict(
                    case_id=self.id, state="REVIEW_READY", created=datetime.now().isoformat(timespec="seconds"),
                    scan=meta, quality=quality,
                    history_files=[dict(name=n, pages=context.pdf_page_count(p) if p.suffix.lower() == ".pdf" else 1) for p, n in self.histories],
                    history_provided=bool(self.histories), warnings=warnings,
                    presentation_text=self.symptoms_text, symptoms=symptoms,
                    timeline=context.build_timeline(events, reconcile.relevant_concepts(findings)),
                    findings=findings, summary=summary, not_assessable=not_assessable, other_observations=other,
                    technical=dict(models=[dict(role=s["role"], model=s["model"]) for s in result["sources"]],
                                   timing=result.get("timing", {}), raw_reasoning=result.get("raw_reasoning") or [],
                                   top_concepts=result.get("top_concepts") or [], total_seconds=round(time.time() - t0, 2), engine_status=dict(engine.status)),
                )
                (self.dir / "result.json").write_text(json.dumps(self.result, indent=2))
            self._step("review", prepare)
            self.state = "REVIEW_READY"
        except Exception as e:
            self._fail("INTERNAL", e)
