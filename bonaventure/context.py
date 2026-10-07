"""Patient-history and current-presentation parsing: concept matching, negation, dates, durations, provenance."""
import re
import subprocess
from pathlib import Path

from .knowledge import HISTORY_CONCEPTS, NORMAL_PHRASES, SYMPTOM_CONCEPTS

# ---------- concept matching ----------

def _compile(concepts):
    return {cid: re.compile(r"\b(?:" + "|".join(spec[-1]) + r")\b", re.I) for cid, spec in concepts.items()}

_HISTORY_RX = _compile(HISTORY_CONCEPTS)
_SYMPTOM_RX = _compile(SYMPTOM_CONCEPTS)
_NORMAL_RX = {cid: re.compile(r"\b(?:" + "|".join(p) + r")\b", re.I) for cid, p in NORMAL_PHRASES.items()}

# NegEx-lite: a pre-trigger negates concepts that follow it within a short window, unless a terminator intervenes.
_NEG_PRE = re.compile(r"\b(?:no|not|denies|denied|deny|denying|without|negative for|absence of|free of|never|nor|rules? out|ruled out for)\b", re.I)
_NEG_POST = re.compile(r"^[\s,]*(?:is |was |has been )?(?:ruled out|excluded|absent|not seen|not present|not identified)\b", re.I)
_NEG_STOP = re.compile(r"\b(?:but|however|although|though|except|reports?|has|have|with|presents?|presented|complains?|admits?|which|now)\b|[.;:]", re.I)
_NEG_WINDOW_WORDS = 8


def _negated(sentence, start, end):
    for trig in _NEG_PRE.finditer(sentence[:start]):
        between = sentence[trig.end():start]
        if not _NEG_STOP.search(between) and len(between.split()) <= _NEG_WINDOW_WORDS:
            return True
    clause_after = re.split(r"[,.;]", sentence[end:], maxsplit=1)[0]
    return bool(_NEG_POST.match(clause_after))


def find_mentions(sentence, rx_table):
    """Return [(concept, start, end, negated)], dropping matches nested inside a longer match."""
    hits = [(cid, m.start(), m.end()) for cid, rx in rx_table.items() for m in rx.finditer(sentence)]
    hits = [h for h in hits if not any(o != h and o[1] <= h[1] and h[2] <= o[2] and (o[2] - o[1]) > (h[2] - h[1]) for o in hits)]
    return [(cid, s, e, _negated(sentence, s, e)) for cid, s, e in sorted(hits, key=lambda h: h[1])]


def sentences(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n(?=[a-z(])", " ", text)  # re-join lines wrapped mid-sentence
    return [s.strip() for s in re.split(r"(?<=[.;!?])\s+|\n+", text) if s.strip()]

# ---------- dates & durations ----------

_MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), lambda g: (int(g[0]), int(g[1]), int(g[2]))),
    (re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"),  # DD/MM/YYYY, falling back to MM/DD when unambiguous
     lambda g: (int(g[2]), int(g[1]), int(g[0])) if int(g[1]) <= 12 else (int(g[2]), int(g[0]), int(g[1]))),
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r",?\s+(\d{4})\b", re.I), lambda g: (int(g[2]), _MONTHS[g[1][:3].lower()], int(g[0]))),
    (re.compile(r"\b" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I), lambda g: (int(g[2]), _MONTHS[g[0][:3].lower()], int(g[1]))),
    (re.compile(r"\b" + _MON + r",?\s+(\d{4})\b", re.I), lambda g: (int(g[1]), _MONTHS[g[0][:3].lower()], None)),
    (re.compile(r"\b(\d{1,2})/(\d{4})\b"), lambda g: (int(g[1]), int(g[0]), None)),
    (re.compile(r"\b(?:in|since|from|year)\s+((?:19|20)\d{2})\b", re.I), lambda g: (int(g[0]), None, None)),
]


def find_dates(text):
    """Return [(position, 'YYYY[-MM[-DD]]')] for every recognisable date, non-overlapping, in text order."""
    found, taken = [], []
    for rx, conv in _DATE_PATTERNS:
        for m in rx.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            try:
                y, mo, d = conv(m.groups())
            except (KeyError, ValueError):
                continue
            if not (1900 <= y <= 2100) or (mo and not 1 <= mo <= 12) or (d and not 1 <= d <= 31):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), f"{y:04d}" + (f"-{mo:02d}" if mo else "") + (f"-{d:02d}" if mo and d else "")))
    return sorted(found)


_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_DURATION = re.compile(r"\b(?:for|since|x|over|past|last)\s+(?:the\s+)?(?:past\s+|last\s+)?(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|few|several|couple of)\s+(hours?|days?|weeks?|months?|years?)\b", re.I)
_DURATION_WORDS = re.compile(r"\bsince (yesterday|last night|this morning|today)\b", re.I)


def find_duration(clause):
    m = _DURATION.search(clause)
    if m:
        n, unit = m.group(1).lower(), m.group(2).lower().rstrip("s")
        n = _NUM.get(n, n)
        return f"{n} {unit}" + ("s" if str(n) not in ("1",) else "")
    m = _DURATION_WORDS.search(clause)
    return f"since {m.group(1).lower()}" if m else None

# ---------- current presentation ----------

def parse_symptoms(text):
    """Free-text presentation -> [{concept, label, state: present|denied, duration, text}] (first mention wins)."""
    out = {}
    for sent in sentences(text or ""):
        for cid, s, e, neg in find_mentions(sent, _SYMPTOM_RX):
            if cid in out:
                continue
            clause = _clause_around(sent, s, e)
            out[cid] = dict(concept=cid, label=SYMPTOM_CONCEPTS[cid][0], state="denied" if neg else "present",
                            duration=None if neg else find_duration(clause), text=sent[s:e])
    return list(out.values())


def _clause_around(sent, s, e):
    left = max(sent.rfind(",", 0, s), sent.rfind(";", 0, s)) + 1
    right = min([i for i in (sent.find(",", e), sent.find(";", e)) if i != -1] or [len(sent)])
    return sent[left:right]

# ---------- patient history documents ----------

_DOC_TYPES = [
    ("discharge summary", "Discharge summary"), ("radiology", "Radiology report"), ("x-ray report", "Radiology report"),
    ("chest radiograph", "Radiology report"), ("impression:", "Radiology report"), ("echocardiogra", "Echo report"),
    ("prescription", "Prescription"), ("progress note", "Progress note"), ("consultation", "Consultation note"),
    ("laboratory", "Lab report"), ("lab report", "Lab report"), ("referral", "Referral letter"),
]


class HistoryParseError(Exception):
    pass


def read_pages(path):
    """Text of each page. PDFs via poppler's pdftotext; plain text is a single page."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        try:
            raw = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=60, check=True).stdout
        except (subprocess.SubprocessError, OSError) as e:
            raise HistoryParseError(f"{path.name}: could not read PDF ({e})") from e
        return raw.split("\f")[:-1] or [raw]
    if path.suffix.lower() in (".txt", ".md", ".text"):
        return [path.read_text(errors="replace")]
    raise HistoryParseError(f"{path.name}: unsupported document type (use PDF or text)")


def pdf_page_count(path):
    try:
        info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=20).stdout
        return int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    except (AttributeError, OSError, subprocess.SubprocessError):
        return None


def doc_type(text, filename):
    head = text[:800].lower()
    for key, label in _DOC_TYPES:
        if key in head:
            return label
    return Path(filename).stem.replace("_", " ").replace("-", " ").strip().capitalize() or "Clinical document"


def parse_history(path, display_name=None):
    """One document -> (events, warnings). Each event keeps its page and verbatim quote for provenance."""
    name = display_name or Path(path).name
    pages = read_pages(path)
    full = "\n".join(pages)
    if not full.strip():
        return [], [f"{name}: no readable text (scanned document? OCR is not supported)"]
    dtype = doc_type(full, name)
    events, last_date = [], None
    for page_no, page in enumerate(pages, 1):
        for sent in sentences(page):
            if len(sent) < 70:  # a short heading naming a document type starts a new section (combined PDFs)
                dtype = next((label for key, label in _DOC_TYPES if key in sent.lower()), dtype)
            dates = find_dates(sent)
            normals = [(cid, m.start(), m.end(), True) for cid, rx in _NORMAL_RX.items() for m in rx.finditer(sent)]
            for cid, s, e, neg in find_mentions(sent, _HISTORY_RX) + normals:
                # nearest date in the sentence, else the most recent date seen earlier in the document
                date = min(dates, key=lambda d: abs(d[0] - s))[1] if dates else last_date
                label, category, _ = HISTORY_CONCEPTS[cid]
                events.append(dict(concept=cid, label=label, category=category, state="negated" if neg else "present",
                                   date=date, source=dict(file=name, path=str(path), doc_type=dtype, page=page_no, quote=_quote(sent, s, e))))
            if dates and len(dates[-1][1]) > 4:  # only month-precise dates (e.g. note headers) carry forward
                last_date = dates[-1][1]
    return events, []


def _quote(sent, s, e, width=200):
    if len(sent) <= width:
        return sent
    a = max(0, min(s - width // 3, len(sent) - width))
    return ("…" if a else "") + sent[a:a + width].strip() + ("…" if a + width < len(sent) else "")


def presentation_as_history(text):
    """Risk factors typed into the presentation ("recent long-haul flight", "on warfarin") count as context too."""
    events = []
    for sent in sentences(text or ""):
        for cid, s, e, neg in find_mentions(sent, _HISTORY_RX):
            label, category, _ = HISTORY_CONCEPTS[cid]
            events.append(dict(concept=cid, label=label, category=category, state="negated" if neg else "present", date=None,
                               source=dict(file="presentation", path="", doc_type="Current presentation", page=1, quote=_quote(sent, s, e))))
    return events


def build_timeline(events, relevant_concepts):
    """Relevant, present events only; one entry per (concept, date), newest first, undated last."""
    seen, out = set(), []
    for ev in events:
        key = (ev["concept"], ev["date"])
        if ev["state"] != "present" or ev["concept"] not in relevant_concepts or key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return sorted(out, key=lambda ev: ev["date"] or "", reverse=True)


if __name__ == "__main__":
    s = {x["concept"]: x for x in parse_symptoms("Shortness of breath for three days, ankle swelling, no fever. Denies chest trauma or cough but has orthopnea.")}
    assert s["dyspnea"]["state"] == "present" and s["dyspnea"]["duration"] == "3 days", s["dyspnea"]
    assert s["peripheral_edema"]["state"] == "present"
    assert s["fever"]["state"] == "denied" and s["trauma"]["state"] == "denied" and s["cough"]["state"] == "denied"
    assert s["orthopnea"]["state"] == "present"
    assert [d for _, d in find_dates("Seen 12/08/2026 and on Aug 3, 2025; CHF since 2019")] == ["2026-08-12", "2025-08-03", "2019"]
    m = find_mentions("Small right-sided pleural effusion. No pneumothorax.", _HISTORY_RX)
    assert [(c, n) for c, _, _, n in m] == [("prior_effusion", False), ("prior_pneumothorax", True)], m
    assert [c for c, *_ in find_mentions("productive cough with sputum", _SYMPTOM_RX)] == ["productive_cough", "productive_cough"]
    print("context ok")
