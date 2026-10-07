"""Case orchestration: run each pipeline stage, track progress for the UI, capture failures, persist the result."""
import json
import re
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
            # same patient? documents (and a DICOM header) must not name different people before any of them is used
            identity = context.check_identity(
                [context.document_identity(p, n) for p, n in self.histories]
                + ([dict(file=meta["file"], name=meta.get("patient_name"), mrn=meta.get("patient_id"))] if meta.get("patient_name") or meta.get("patient_id") else []))
            if identity["status"] == "mismatch":
                warnings.append("History not used: " + identity["message"])
                events = []
            if not self.histories:
                self.steps["history"] = "skipped"
            def understand():
                """MedGemma reads every phrase and rewrites it in clinical language; the deterministic parser maps the rewrite to
                concepts (auditable); the rules' own reading of the clinician's words checks it. Disagreements keep the safer
                reading and are shown. Phrases nothing understood are reported, never silently dropped."""
                from .knowledge import HISTORY_CONCEPTS, SYMPTOM_CONCEPTS
                from . import semantic
                text = self.symptoms_text
                clauses = [c.strip() for c in re.split(r"[,.;]|\band\b", text) if len(c.strip().split()) >= 2]
                mg = None if engine.mock else (engine.models.get("reasoning") if engine.ready() else None)
                rewrites = [""] * len(clauses)
                if mg and clauses:
                    with engine._lock:
                        rewrites, self._nl_raw = mg.rewrite_clinical(clauses)

                found, hx, flags, unrecognised, have = [], [], [], [], {}

                def add(kind, cid, state, clause, how, duration=None):
                    if cid in have:
                        return
                    have[cid] = state
                    if kind == "symptom":
                        found.append(dict(concept=cid, label=SYMPTOM_CONCEPTS[cid][0], state=state, duration=duration, text=clause, source=how))
                    else:
                        label, category, _ = HISTORY_CONCEPTS[cid]
                        hx.append(dict(concept=cid, label=label, category=category, state="present" if state == "present" else "negated", date=None,
                                       source=dict(file="presentation", path="", doc_type="Current presentation", page=1, quote=clause)))

                def read(t):
                    out = {x["concept"]: ("symptom", x["state"], x.get("duration")) for x in context.parse_symptoms(t)}
                    out.update({e["concept"]: ("history", "present" if e["state"] == "present" else "denied", None) for e in context.presentation_as_history(t)})
                    return out

                for clause, rw in zip(clauses, rewrites):
                    rules, model = read(clause), read(rw) if rw else {}
                    for cid, (kind, state, dur) in rules.items():
                        m = model.get(cid)
                        if m and m[1] != state:   # MedGemma and the rules disagree (usually a lost "no"): keep the rules, show it
                            flags.append(f"“{clause}”: read as {state} {SYMPTOM_CONCEPTS.get(cid, HISTORY_CONCEPTS.get(cid))[0].lower()}, "
                                         f"but the clinical rewrite (“{rw}”) says {m[1]} — please check")
                        add(kind, cid, state, clause, f"“{clause}”" + (f" → {rw} (MedGemma agrees)" if m and m[1] == state else ""), dur)
                    rules_saw_symptom = any(k == "symptom" for k, _s, _d in rules.values())
                    for cid, (kind, state, dur) in model.items():
                        # where the rules already read a symptom in this phrase, MedGemma's extra symptoms are looser paraphrase
                        if cid not in rules and not (kind == "symptom" and rules_saw_symptom):
                            add(kind, cid, state, clause, f"understood by MedGemma: “{clause}” → {rw}", dur)
                    if not rules and not model and semantic.matcher():
                        m = semantic.matcher().match(rw or clause) or semantic.matcher().match(clause)
                        if m:
                            denied = bool(re.match(r"\s*(?:no|not|never|denies|denied|without)\b", clause, re.I))
                            add(m[0], m[1], "denied" if denied else "present", clause, f"matched by meaning ({m[2]:.2f}): “{clause}”")
                            continue
                    if not rules and not model:
                        unrecognised.append(clause)
                # whole-text rules catch anything split across phrases (durations, multi-clause negation)
                for cid, (kind, state, dur) in read(text).items():
                    add(kind, cid, state, text, "rules")
                for x in found:  # durations are only visible to the rules on the full sentence
                    if not x.get("duration"):
                        x["duration"] = next((y["duration"] for y in context.parse_symptoms(text) if y["concept"] == x["concept"]), None)
                if any(x["concept"] == "productive_cough" for x in found):   # "cough" is implied by "productive cough"
                    found = [x for x in found if x["concept"] != "cough"]
                self._unrecognised, self._nl_flags = unrecognised, flags
                return found, hx
            symptoms, presented = self._step("symptoms", understand)
            events += presented

            try:
                result = self._step("image", lambda: engine.analyze(img, self.scan))
            except Exception as e:
                return self._fail("IMAGE_MODEL_FAILED", e)
            self._step("localize", lambda: None)  # localization is produced alongside the image analysis

            findings, summary = self._step("reconcile", lambda: reconcile.reconcile(result, quality, symptoms, events, bool(self.histories)))
            not_assessable = reconcile.not_assessable(symptoms, events)
            other = reconcile.other_observations(result, findings)
            reliable = {f for s in result["sources"] for f, ok in s.get("reliable", {}).items() if ok}
            interval = reconcile.interval_changes(findings, events, identity, reliable)

            def prepare():
                preview = img.copy()
                preview.thumbnail((1600, 1600))
                preview.save(self.dir / "scan.png")
                self.result = dict(
                    case_id=self.id, state="REVIEW_READY", created=datetime.now().isoformat(timespec="seconds"),
                    scan=meta, quality=quality,
                    history_files=[dict(name=n, pages=context.pdf_page_count(p) if p.suffix.lower() == ".pdf" else 1) for p, n in self.histories],
                    history_provided=bool(self.histories) and identity["status"] != "mismatch", warnings=warnings,
                    identity=identity, interval=interval, rejected=result.get("rejected", []),
                    unrecognised=getattr(self, "_unrecognised", []), understanding_flags=getattr(self, "_nl_flags", []),
                    presentation_text=self.symptoms_text, symptoms=symptoms,
                    timeline=context.build_timeline(events, reconcile.relevant_concepts(findings)),
                    findings=findings, summary=summary, not_assessable=not_assessable, other_observations=other,
                    technical=dict(models=[dict(role=s["role"], model=s["model"]) for s in result["sources"]],
                                   timing=result.get("timing", {}), raw_reasoning=(result.get("raw_reasoning") or []) + ([f"[natural-language understanding] {self._nl_raw}"] if getattr(self, "_nl_raw", None) else []),
                                   top_concepts=result.get("top_concepts") or [], total_seconds=round(time.time() - t0, 2), engine_status=dict(engine.status)),
                )
                (self.dir / "result.json").write_text(json.dumps(self.result, indent=2))
            self._step("review", prepare)
            self.state = "REVIEW_READY"
        except Exception as e:
            self._fail("INTERNAL", e)
