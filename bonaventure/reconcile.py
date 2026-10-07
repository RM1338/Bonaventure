"""Evidence reconciliation: image signals x verifier x quality x history x presentation -> evidence state per finding.

Rules are explicit on purpose: every status carries the reasons that produced it.
"""
from .knowledge import FINDINGS, HISTORY_CONCEPTS, NOT_ASSESSABLE, RESOLVE, SUPPRESSED_BY, SYMPTOM_CONCEPTS, ZONE_NAMES, ZONES, region_zones

LEVELS = ["absent", "weak", "moderate", "strong"]
_ORDER = {"SUPPORTED": 0, "CONFLICTING": 1, "UNCERTAIN": 2, "INSUFFICIENT_EVIDENCE": 3}


def level(score, thresholds):
    return LEVELS[sum(score >= t for t in thresholds)]


def _thr(source, fid):
    """Per-finding calibrated thresholds; older/mock sources carry one list for every finding."""
    t = source["thresholds"]
    return t[fid] if isinstance(t, dict) else t


def _concept_source(fid, cr, concepts):
    """The concept bank as a reader: rank of the best matching phrase mapped onto the same weak/moderate/strong scale."""
    import math
    hits = concepts.get(fid, {}).get("for", [])
    rank = hits[0][1] if hits else 10**6
    to_score = lambda r: round(max(0.0, 1 - math.log10(max(r, 1)) / 6), 4)   # rank 1 -> 1.0, rank 10^6 -> 0
    return dict(role="concepts", model="CLEAR concepts", scores={fid: to_score(rank)},
                thresholds={fid: [to_score(cr["weak"]), to_score(cr["moderate"]), to_score(cr["strong"])]}, reliable={fid: True})


def calibrated(source, fid, score):
    """Reader's calibrated probability (0-100 %) that the finding is present, from Platt scaling on labelled films; None if uncalibrated."""
    import math
    c = (source or {}).get("platt", {}).get(fid)
    if c is None or score is None:
        return None
    x = math.log(min(max(score, 1e-6), 1 - 1e-6) / (1 - min(max(score, 1e-6), 1 - 1e-6)))
    return round(100 / (1 + math.exp(-(c["a"] * x + c["b"]))))


def _image_agreement(p, v):
    """p, v are levels (v may be None when no verifier ran)."""
    rp = LEVELS.index(p)
    if v is None:
        return "partial" if rp >= 2 else "weak"
    rv = LEVELS.index(v)
    if rp >= 2 and rv >= 2:
        return "concordant"
    if max(rp, rv) >= 2 and min(rp, rv) == 0:
        return "discordant"
    return "partial" if max(rp, rv) >= 2 else "weak"


def reconcile(imaging, quality, symptoms, history_events, history_provided):
    src = {s["role"]: s for s in imaging["sources"]}
    roles = (src.get("primary") or src.get("verifier"), src.get("verifier") if src.get("primary") else None)
    findings = []
    for fid, spec in FINDINGS.items():
        # only readers that proved reliable for this finding on labelled data get a vote
        voters = [x for x in roles if x and x.get("reliable", {}).get(fid, True)]
        cr = imaging.get("concept_reader", {}).get(fid, {})
        if not voters and cr.get("reliable") and imaging.get("concepts"):
            voters = [_concept_source(fid, cr, imaging["concepts"])]  # e.g. emphysema: only the concept bank reads it well
        if not voters:
            continue  # no reliable image reader: may still surface via the open-ended survey, never as a finding
        primary, verifier = voters[0], (voters[1] if len(voters) > 1 else None)
        p_score = primary["scores"].get(fid, 0.0)
        p = level(p_score, _thr(primary, fid))
        v_score = verifier["scores"].get(fid) if verifier else None
        v = level(v_score, _thr(verifier, fid)) if v_score is not None else None
        levels = [LEVELS.index(p)] + ([LEVELS.index(v)] if v is not None else [])
        candidate = levels[0] >= 3 if len(levels) == 1 else (max(levels) >= 2 or min(levels) >= 1)
        if not candidate and fid not in imaging["localizations"]:
            continue  # not a candidate: no reader at moderate, and the readers do not both see something
        f = _assess(fid, spec, p, p_score, v, v_score, primary, verifier, imaging, quality, symptoms, history_events, history_provided)
        if f:
            findings.append(f)
    raised = {f["canonical_name"] for f in findings}
    for f in findings:
        if SUPPRESSED_BY.get(f["canonical_name"]) in raised:
            imaging.setdefault("rejected", []).append(dict(claim=f["display_name"], by="label hierarchy",
                reason=f"already explained by {FINDINGS[SUPPRESSED_BY[f['canonical_name']]]['name'].lower()}"))
    findings = [f for f in findings if SUPPRESSED_BY.get(f["canonical_name"]) not in raised]
    findings.sort(key=lambda f: (_ORDER[f["status"]], f["_rank"], -f["_score"]))
    for i, f in enumerate(findings, 1):
        f["id"] = f"finding_{i:02d}"
        f.pop("_score")
        f.pop("_rank")
    return findings, _summary(findings, quality)


def _assess(fid, spec, p, p_score, v, v_score, primary, verifier, imaging, quality, symptoms, events, history_provided):
    hist_for = _dedupe([e for e in events if e["concept"] in spec["history"] and e["state"] == "present"])
    # most specific first: the finding's own prior-imaging concept leads its history list
    hist_against = sorted(_dedupe([e for e in events if e["concept"] in spec["history"] and e["state"] == "negated"]),
                          key=lambda e: spec["history"].index(e["concept"]))
    sym_for = [s for s in symptoms if s["concept"] in spec["symptoms"] and s["state"] == "present"]
    sym_against = [s for s in symptoms if s["concept"] in spec["symptoms"] and s["state"] == "denied"]
    key_denied = [s for s in sym_against if s["concept"] in spec["key_against"]]
    support = len({e["concept"] for e in hist_for}) + len(sym_for)
    against = len({e["concept"] for e in hist_against}) + len(sym_against)

    concept = imaging.get("concepts", {}).get(fid, {})
    agreement = _image_agreement(p, v)
    desc = imaging["descriptions"].get(fid)
    mg_sees = None if desc is None else not any("did not identify" in t for t in desc)  # None: MedGemma was not asked
    if any(o.get("maps_to") == fid and o.get("verified", True) for o in imaging.get("other_findings", [])):
        mg_sees = True  # named it unprompted in the open-ended survey, and CLEAR agreed
    if agreement == "partial" and mg_sees:
        agreement = "concordant"  # majority of three readers: one image model clearly + MedGemma, the other leaning the same way
    loc = imaging["localizations"].get(fid)
    region = (loc or {}).get("region_name") or imaging.get("regions", {}).get(fid) or spec["region"]
    contradictions, notes = [], []

    # CLEAR's concept retrieval ranks the film against 368,294 report phrases. On sick films the prompt-pair scores saturate
    # for every finding; the rank of the best matching phrase is what stays specific.
    cr = imaging.get("concept_reader", {}).get(fid)
    # the gate only applies where the concept bank itself proved reliable (it is poor at cardiomegaly / mediastinum);
    # without measurements (older setups) every finding is gated as before
    concepts_ran = bool(imaging.get("concepts")) and (cr is None or cr.get("reliable", False)) and primary["model"] != "CLEAR concepts"
    best_rank = (concept.get("for") or [[None, 10**9]])[0][1]
    survey_named = any(o.get("maps_to") == fid and o.get("verified", True) for o in imaging.get("other_findings", []))
    gate_drop = max(300, cr["weak"]) if cr else 300
    if concepts_ran and best_rank > gate_drop and not survey_named:
        if max(LEVELS.index(p), LEVELS.index(v or "absent")) >= 2:
            imaging.setdefault("rejected", []).append(dict(
                claim=spec["name"], by=" + ".join(x["model"] for x in (primary, verifier) if x),
                reason="prompt score was high, but no phrase among the film's top 300 of 368,294 report phrases names it"
                       + (f" (best #{best_rank})" if best_rank < 10**9 else "")))
        return None  # nothing in the film's top 300 phrases speaks for it: not a finding
    concept_cap = concepts_ran and best_rank > (cr["moderate"] if cr else 25)
    if concepts_ran and best_rank <= (cr["strong"] if cr else 10):  # the film's closest report phrases name it: a third image reader saying yes
        agreement = {"weak": "partial", "partial": "concordant"}.get(agreement, agreement) if mg_sees is not False else agreement

    if primary["model"] == "CLEAR concepts":
        # a finding only the concept bank reads (emphysema, fibrosis) needs a second, independent reader: MedGemma must see it
        if mg_sees is not True:
            imaging.setdefault("rejected", []).append(dict(claim=spec["name"], by="CLEAR concepts",
                reason="the film's closest report phrases suggest it, but MedGemma did not confirm it on the image"))
            return None
        if not hist_for:  # language retrieval + MedGemma alone also fire on normal films: the patient's record must agree
            imaging.setdefault("rejected", []).append(dict(claim=spec["name"], by="CLEAR concepts + MedGemma",
                reason="nothing in the patient's history points to it (e.g. COPD, ILD, asbestos), so it is not raised"))
            return None

    if quality["state"] == "poor":
        status = "INSUFFICIENT_EVIDENCE"
        notes.append("Image quality prevents reliable assessment.")
    elif agreement == "discordant" and mg_sees:
        # MedGemma breaks the tie: two of three readers see it -> not a conflict, but not settled either
        status = "UNCERTAIN"
        notes.append(f"Readers split 2–1: {'CLEAR' if LEVELS.index(p) >= 2 else 'CheXzero'} and MedGemma see it, "
                     f"{'CheXzero' if LEVELS.index(p) >= 2 else 'CLEAR'} does not.")
    elif agreement == "discordant":
        status = "CONFLICTING"
        contradictions.append(f"Image models disagree: primary signal {p}, independent verifier {v}"
                              + (", and MedGemma does not see it." if mg_sees is False else "."))
    elif agreement in ("concordant", "partial") and hist_against and not hist_for:
        status = "CONFLICTING"
        e = hist_against[0]
        contradictions.append(f"Image signal present, but the patient's records argue against it: {e['source']['doc_type'].lower()}"
                              f"{' (' + e['date'] + ')' if e['date'] else ''} states “{e['source']['quote']}”")
    elif agreement in ("concordant", "partial") and key_denied and len(key_denied) >= support:
        status = "CONFLICTING"
        contradictions.append("Image signal present, but the current presentation argues against it: "
                              + ", ".join(f"{s['label'].lower()} denied" for s in key_denied) + ".")
    elif agreement == "concordant":
        # the thesis: pixels alone never make a finding "supported" — the patient has to agree (devices are hardware, exempt)
        # devices are hardware, exempt from the context rule, but MedGemma must name one unprompted (and CLEAR agree):
        # asked "is there a line?", it tends to say yes
        status = "SUPPORTED" if support >= 1 or (spec.get("context_free") and survey_named) else "UNCERTAIN"
    elif agreement == "partial":
        status = "SUPPORTED" if support >= 2 else "UNCERTAIN"
        if v is not None:
            notes.append("Independent verifier signal is only weak.")
    else:
        status = "UNCERTAIN" if support >= 1 else "INSUFFICIENT_EVIDENCE"
        notes.append("Image signal is weak.")
    if primary["model"] == "CLEAR concepts" and status == "SUPPORTED" and support == 0:
        status = "UNCERTAIN"
        notes.append("Read by the concept bank and MedGemma only; nothing in the history supports it.")
    if concept_cap and status == "SUPPORTED":
        status = "UNCERTAIN"
        notes.append("CLEAR's concept retrieval only weakly backs this" + (f" (best matching phrase ranked #{best_rank})." if best_rank < 10**9 else "."))
    # bare film (no history, no presentation): only what both image models agree on, or what MedGemma names unprompted and
    # CLEAR confirms, is shown; a one-reader signal with nothing else behind it goes to the rejected log
    if (not history_provided and not symptoms and status != "SUPPORTED" and quality["state"] != "poor"
            and agreement != "concordant" and not survey_named):
        imaging.setdefault("rejected", []).append(dict(claim=spec["name"], by=" + ".join(x["model"] for x in (primary, verifier) if x),
            reason=f"image readers {agreement} ({p}/{v or '—'}), no history or presentation supplied, and MedGemma did not name it unprompted"))
        return None
    if status == "UNCERTAIN" and support == 0:
        notes.append("No supporting clinical context identified.")

    img_points = {"concordant": 2.5 + 0.5 * (p == v == "strong"), "partial": 1.5, "discordant": 1.0, "weak": 0.5}[agreement]
    score = img_points + 0.5 * min(support, 3) - 0.5 * against - (0.5 if quality["state"] == "limited" else 0)
    if quality["state"] == "limited":
        notes.append("Evidence strength reduced for image quality: " + " ".join(quality["warnings"]))
    # "high" needs the patient as well as the pixels: image agreement alone tops out at moderate
    strength = ("high" if score >= 3 and status == "SUPPORTED" and support >= 1 else
                "moderate" if score >= 2 and status != "INSUFFICIENT_EVIDENCE" else "low")

    image_evidence = [dict(text=t, source="description", level="absent" if "did not identify" in t else None) for t in imaging["descriptions"].get(fid, [])]
    image_evidence.append(dict(text=f"Primary image signal: {p}", source=primary["model"], level=p))
    if verifier:
        image_evidence.append(dict(text=f"Independent verifier: {v}", source=verifier["model"], level=v))
    image_evidence += [dict(text=f"“{c[0]}”", source="CLEAR concept", rank=c[1], level="strong" if c[1] <= 100 else "moderate") for c in concept.get("for", [])[:2]]
    if loc:
        image_evidence.append(dict(text=f"Localized to {region}" + (" · segmented" if loc.get("contour") else ""), source=loc.get("source", "")))

    negative = [dict(text=f"No {e['label'].lower()} — {e['source']['doc_type']}", kind="history", source=e["source"], date=e["date"]) for e in hist_against]
    negative += [dict(text=f"{s['label']} denied", kind="symptom", concept=s["concept"]) for s in sym_against]
    negative += [dict(text=f"Film also resembles “{c[0]}”", kind="image", rank=c[1]) for c in concept.get("against", [])[:1] if c[1] <= 150]

    return dict(
        canonical_name=fid, display_name=spec["name"], status=status, evidence_strength=strength, _score=score, _rank=best_rank,
        localization=(dict(type="contour" if loc.get("contour") else "bbox", coordinates=loc["bbox"], contour=loc.get("contour"),
                           region_name=region, source=loc.get("source"), zones=region_zones(region)) if loc
                      else _zone_localization(region) if status != "INSUFFICIENT_EVIDENCE" else None),
        mask=imaging.get("masks", {}).get(fid),
        image_evidence=image_evidence,
        history_evidence=[dict(text=e["label"], concept=e["concept"], date=e["date"], category=e["category"], source=e["source"]) for e in hist_for],
        symptom_evidence=[dict(text=s["label"], concept=s["concept"], duration=s["duration"]) for s in sym_for],
        negative_evidence=negative,
        contradictions=contradictions,
        notes=notes,
        signals=dict(
            image=p, verifier=v, agreement=agreement,
            history="present" if hist_for else "against" if hist_against else "none" if history_provided else "not provided",
            symptoms="present" if sym_for else "against" if sym_against else "none"),
        contribution=dict(image=round(p_score, 3), verifier=None if v_score is None else round(v_score, 3),
                          context=round(support / (support + against), 2) if support + against else 0.0),
        technical=dict(primary_model=primary["model"], primary_score=round(p_score, 4), thresholds=_thr(primary, fid),
                       verifier_thresholds=_thr(verifier, fid) if verifier else None,
                       verifier_model=verifier["model"] if verifier else None, verifier_score=None if v_score is None else round(v_score, 4),
                       localization_source=(loc or {}).get("source"), support_count=support, against_count=against),
        confidence=_confidence(fid, primary, p_score, verifier, v_score),
        clinician_text=_clinician_text(spec["name"], status, region, agreement, support, mg_sees),
    )


def _confidence(fid, primary, p_score, verifier, v_score):
    """Image confidence as a percentage: mean of the voting readers' calibrated probabilities. Image only; the patient's
    context is weighed by the evidence state, not folded into this number."""
    readers = {x["model"]: calibrated(x, fid, sc) for x, sc in ((primary, p_score), (verifier, v_score)) if x}
    readers = {m: v for m, v in readers.items() if v is not None}
    if not readers:
        return None
    c = next(x["platt"][fid] for x in (primary, verifier) if x and fid in x.get("platt", {}))
    return dict(image=round(sum(readers.values()) / len(readers)), readers=readers,
                basis=f"calibrated on {c['n']} labelled films ({c['source']})")


def _zone_localization(region):
    """No trustworthy model outline: point at the anatomical zone(s) the region text names. Marked approximate in the UI."""
    zones = region_zones(region)
    boxes = [ZONES[z] for z in zones]
    union = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    return dict(type="zone", coordinates=union, zones=zones, zone_boxes=boxes, contour=None,
                region_name=region if region else ", ".join(ZONE_NAMES[z] for z in zones), source="approximate zone")


def _dedupe(events):
    seen, out = set(), []
    for e in sorted(events, key=lambda e: e["date"] or "", reverse=True):
        if (e["concept"], e["date"]) not in seen:
            seen.add((e["concept"], e["date"]))
            out.append(e)
    return out


def _clinician_text(name, status, region, agreement, support, mg_sees=None):
    n = name.lower()
    if status == "SUPPORTED":
        why = "Imaging and the supplied context agree." if support else "Both image models agree; there is no clinical context to weigh it against."
        if mg_sees is False:
            why += " The visual reasoning model did not describe it — check the film."
        return f"Consider {n} ({region}). {why}"
    return {
        "CONFLICTING": f"Evidence for {n} is inconsistent. Human review required.",
        "UNCERTAIN": f"Possible {n} ({region}); evidence is limited. Correlate clinically.",
        "INSUFFICIENT_EVIDENCE": f"{name} cannot be reliably assessed from the supplied evidence.",
    }[status]


def _summary(findings, quality):
    counts = {s: sum(f["status"] == s for f in findings) for s in _ORDER}
    critical = sum(f["canonical_name"] == "PNEUMOTHORAX" and f["status"] in ("SUPPORTED", "CONFLICTING") for f in findings)
    overall = "low" if quality["state"] == "poor" else "moderate" if quality["state"] == "limited" or counts["CONFLICTING"] else "high"
    return dict(total=len(findings), counts=counts, critical=critical, overall_quality=overall,
                message=None if counts["SUPPORTED"] else "No sufficiently supported finding was identified from the supplied evidence.")


def not_assessable(symptoms, events):
    """Conditions the context raises but a chest X-ray cannot settle (e.g. pulmonary embolism) -> advisory, never a finding."""
    present_sym = {s["concept"]: s for s in symptoms if s["state"] == "present"}
    present_hx = {}
    for e in events:
        if e["state"] == "present":
            present_hx.setdefault(e["concept"], e)
    out = []
    for cid, spec in NOT_ASSESSABLE.items():
        hits = [present_sym[c]["label"] for c in spec["triggers"]["symptoms"] if c in present_sym]
        hits += [present_hx[c]["label"] for c in spec["triggers"]["history"] if c in present_hx]
        direct = any(c in present_sym or c in present_hx for c in spec["direct"])
        specific = any(c in present_sym or c in present_hx for c in spec.get("specific", []))
        if direct or (specific and len(hits) >= spec["min_triggers"]):
            out.append(dict(id=cid, name=spec["name"], because=hits, advice=spec["advice"]))
    return out


def other_observations(imaging, findings):
    """Abnormalities a reader raised outside the catalogue. Single reader, unverified: shown, never reconciled."""
    known = {f["canonical_name"] for f in findings}
    # shown only when a second reader (CLEAR, open-vocabulary) agrees; MedGemma alone invents masses and lines on normal films
    return [o for o in imaging.get("other_findings", []) if o.get("maps_to") not in known and o.get("verified", True)]


# which prior-report concept describes the same thing as today's finding
PRIOR_OF = {"PLEURAL_EFFUSION": "prior_effusion", "CARDIOMEGALY": "prior_cardiomegaly", "PNEUMOTHORAX": "prior_pneumothorax",
            "PULMONARY_EDEMA": "prior_edema", "ATELECTASIS": "prior_atelectasis", "CONSOLIDATION": "pneumonia",
            "PNEUMONIA": "pneumonia", "LUNG_MASS": "prior_nodule", "LUNG_NODULE": "prior_nodule"}


def interval_changes(findings, events, identity, reliable_findings):
    """Today's film vs the most recent prior radiology report of the SAME patient (identity must not be a mismatch).
    NEW: prior report said absent, raised now. KNOWN: in the prior report and raised now. NOT SEEN NOW: in the prior report,
    not raised today — only claimed for findings the image models are reliable on."""
    if identity.get("status") == "mismatch":
        return dict(status="blocked", reason=identity["message"], rows=[])
    prior = {}
    for e in events:
        if e["source"].get("doc_type") != "Radiology report" or not e["date"]:
            continue
        if e["concept"] not in prior or e["date"] > prior[e["concept"]]["date"]:
            prior[e["concept"]] = e
    if not prior:
        return dict(status="none", reason="No dated prior radiology report in the supplied records.", rows=[])
    now = {f["canonical_name"]: f for f in findings if f["status"] in ("SUPPORTED", "UNCERTAIN", "CONFLICTING")}
    rows = []
    for fid, concept in PRIOR_OF.items():
        e = prior.get(concept)
        if not e:
            continue
        was = e["state"] == "present"
        cur = now.get(fid)
        if cur and not was:
            change = "NEW"
        elif cur and was:
            change = "KNOWN"
        elif was and fid in reliable_findings:
            change = "NOT SEEN NOW"
        else:
            continue
        rows.append(dict(finding=FINDINGS[fid]["name"], change=change, now=cur["status"] if cur else None,
                         prior_date=e["date"], prior_quote=e["source"]["quote"], prior_file=e["source"]["file"], prior_page=e["source"]["page"]))
    order = {"NEW": 0, "NOT SEEN NOW": 1, "KNOWN": 2}
    rows.sort(key=lambda r: order[r["change"]])
    return dict(status="ok", reason=None, rows=rows, compared_to=max(e["date"] for e in prior.values()))


def discuss(f, verdict, quality, second_look=None):
    """A clinician disagrees. Lay out, from the evidence already gathered, what agrees with them and what does not.
    verdict: 'absent' (clinician thinks it is not there) or 'present' (clinician thinks it is). Never overrules the clinician."""
    lv = {"strong": 3, "moderate": 2, "weak": 1, "absent": 0, None: None}
    sees, doubts = [], []
    t = f["technical"]
    for model, level in ((t["primary_model"], f["signals"]["image"]), (t.get("verifier_model"), f["signals"]["verifier"])):
        if model and level is not None:
            (sees if lv[level] >= 2 else doubts).append(f"{model} reads the image as {level}")
    for e in f["image_evidence"]:
        if e["source"] == "description":
            (doubts if e.get("level") == "absent" else sees).append(f"MedGemma: {e['text']}")
        elif e["source"] == "CLEAR concept":
            sees.append(f"Report phrase {e['text']} is #{e['rank']} of 368,294 closest to this film")
    sees += [f"History: {e['text']} ({e['source']['doc_type']}, page {e['source']['page']})" for e in f["history_evidence"]]
    sees += [f"Presentation: {s['text']}" + (f" for {s['duration']}" if s.get("duration") else "") for s in f["symptom_evidence"]]
    doubts += [n["text"] for n in f["negative_evidence"]] + f["contradictions"]
    doubts += [n for n in f["notes"] if not n.startswith("Evidence strength reduced")]
    if quality.get("state") != "acceptable":
        doubts.append(f"Image quality is {quality['state']}: {' '.join(quality.get('warnings', []))}")
    if second_look is not None:
        (sees if second_look["visible"] else doubts).append(f"MedGemma, asked to look again with your reasoning: {second_look['reason']}")
    agree, against = (doubts, sees) if verdict == "absent" else (sees, doubts)
    if len(agree) >= len(against):
        lean = "The evidence Bonaventure gathered is consistent with your read."
    else:
        lean = (f"Most of the evidence Bonaventure gathered points the other way ({len(against)} items against {len(agree)}). "
                f"Your clinical judgement takes precedence; the items below are what you may want to reconcile.")
    return dict(verdict=verdict, agree=agree, against=against, lean=lean,
                resolve=f"What would settle it: {RESOLVE.get(f['canonical_name'], 'further imaging')}.")


def relevant_concepts(findings):
    """History concepts worth showing on the timeline: those bearing on any candidate finding (all if none)."""
    if not findings:
        return set(HISTORY_CONCEPTS)
    return {c for f in findings for c in FINDINGS[f["canonical_name"]]["history"]} | {c for n in NOT_ASSESSABLE.values() for c in n["triggers"]["history"]}


if __name__ == "__main__":
    q = dict(state="acceptable", warnings=[])
    img = dict(sources=[dict(role="primary", model="P", scores={"PLEURAL_EFFUSION": .8, "PNEUMOTHORAX": .7, "CONSOLIDATION": .7}, thresholds=[.45, .55, .65]),
                        dict(role="verifier", model="V", scores={"PLEURAL_EFFUSION": .7, "PNEUMOTHORAX": .3, "CONSOLIDATION": .6}, thresholds=[.45, .55, .65])],
               localizations={}, descriptions={}, masks={})
    ev = [dict(concept="chf", label="CHF", category="Diagnosis", state="present", date="2025-01", source=dict(doc_type="Discharge summary"))]
    sym = [dict(concept="dyspnea", label="Shortness of breath", state="present", duration=None),
           dict(concept="fever", label="Fever", state="denied", duration=None), dict(concept="cough", label="Cough", state="denied", duration=None)]
    fs, summ = reconcile(img, q, sym, ev, True)
    by = {f["canonical_name"]: f["status"] for f in fs}
    assert by == {"PLEURAL_EFFUSION": "SUPPORTED", "PNEUMOTHORAX": "CONFLICTING", "CONSOLIDATION": "CONFLICTING"}, by
    neg = [dict(concept="prior_effusion", label="Pleural effusion", category="Imaging", state="negated", date="2026-09-02",
                source=dict(doc_type="Radiology report", quote="No pleural effusion.", file="h.pdf", page=2))]
    fs, _ = reconcile(img, q, sym, neg, True)
    assert {f["canonical_name"]: f["status"] for f in fs}["PLEURAL_EFFUSION"] == "CONFLICTING"
    from .context import parse_symptoms, presentation_as_history
    text = "Sudden pleuritic chest pain and palpitations after a long-haul flight."
    na = not_assessable(parse_symptoms(text), presentation_as_history(text))
    assert [n["id"] for n in na] == ["PULMONARY_EMBOLISM"], na
    assert not not_assessable(parse_symptoms("Cough and fever for 3 days."), [])
    fs, _ = reconcile(img, dict(state="poor", warnings=["x"]), sym, ev, True)
    assert all(f["status"] == "INSUFFICIENT_EVIDENCE" for f in fs)
    # bare film, no context, MedGemma silent: a partial signal is dropped (and logged), not shown as a finding
    bare = dict(sources=[dict(role="primary", model="P", scores={"ATELECTASIS": .6}, thresholds=[.45, .55, .65]),
                         dict(role="verifier", model="V", scores={"ATELECTASIS": .5}, thresholds=[.45, .55, .65])], localizations={}, descriptions={}, masks={})
    fs, _ = reconcile(bare, q, [], [], False)
    assert not fs and bare["rejected"][0]["claim"] == "Atelectasis", fs
    # a device both image models see is not SUPPORTED until MedGemma confirms it
    dev = lambda desc: dict(sources=[dict(role="primary", model="P", scores={"SUPPORT_DEVICES": .9}, thresholds=[.45, .55, .65]),
                                     dict(role="verifier", model="V", scores={"SUPPORT_DEVICES": .9}, thresholds=[.45, .55, .65])],
                            localizations={}, descriptions=desc, masks={})
    assert reconcile(dev({"SUPPORT_DEVICES": ["Right-sided central venous catheter"]}), q, sym, [], False)[0][0]["status"] == "UNCERTAIN"  # prompted yes is not enough
    named = dev({}); named["other_findings"] = [dict(name="Central venous catheter", maps_to="SUPPORT_DEVICES", verified=True)]
    assert reconcile(named, q, sym, [], False)[0][0]["status"] == "SUPPORTED"
    print("reconcile ok", by)
