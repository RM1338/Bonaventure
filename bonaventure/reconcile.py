"""Evidence reconciliation: image signals x verifier x quality x history x presentation -> evidence state per finding.

Rules are explicit on purpose: every status carries the reasons that produced it.
"""
from .knowledge import FINDINGS, HISTORY_CONCEPTS, NOT_ASSESSABLE, SUPPRESSED_BY, SYMPTOM_CONCEPTS

LEVELS = ["absent", "weak", "moderate", "strong"]
_ORDER = {"SUPPORTED": 0, "CONFLICTING": 1, "UNCERTAIN": 2, "INSUFFICIENT_EVIDENCE": 3}


def level(score, thresholds):
    return LEVELS[sum(score >= t for t in thresholds)]


def _thr(source, fid):
    """Per-finding calibrated thresholds; older/mock sources carry one list for every finding."""
    t = source["thresholds"]
    return t[fid] if isinstance(t, dict) else t


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
    concepts_ran = bool(imaging.get("concepts"))
    best_rank = (concept.get("for") or [[None, 10**9]])[0][1]
    survey_named = any(o.get("maps_to") == fid and o.get("verified", True) for o in imaging.get("other_findings", []))
    if concepts_ran and best_rank > 300 and not survey_named:
        return None  # nothing in the film's top 300 phrases speaks for it: not a finding
    concept_cap = concepts_ran and best_rank > 25
    if best_rank <= 10:  # the film's closest report phrases name it: a third image reader saying yes
        agreement = {"weak": "partial", "partial": "concordant"}.get(agreement, agreement) if mg_sees is not False else agreement

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
        status = "SUPPORTED" if support >= 1 or (p == v == "strong") or spec.get("context_free") else "UNCERTAIN"
    elif agreement == "partial":
        status = "SUPPORTED" if support >= 2 else "UNCERTAIN"
        if v is not None:
            notes.append("Independent verifier signal is only weak.")
    else:
        status = "UNCERTAIN" if support >= 1 else "INSUFFICIENT_EVIDENCE"
        notes.append("Image signal is weak.")
    if concept_cap and status == "SUPPORTED":
        status = "UNCERTAIN"
        notes.append("CLEAR's concept retrieval only weakly backs this" + (f" (best matching phrase ranked #{best_rank})." if best_rank < 10**9 else "."))
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
        localization=dict(type="contour" if loc.get("contour") else "bbox", coordinates=loc["bbox"], contour=loc.get("contour"),
                          region_name=region, source=loc.get("source")) if loc else None,
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
        clinician_text=_clinician_text(spec["name"], status, region, agreement, support, mg_sees),
    )


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
        if direct or len(hits) >= spec["min_triggers"]:
            out.append(dict(id=cid, name=spec["name"], because=hits, advice=spec["advice"]))
    return out


def other_observations(imaging, findings):
    """Abnormalities a reader raised outside the catalogue. Single reader, unverified: shown, never reconciled."""
    known = {f["canonical_name"] for f in findings}
    # shown only when a second reader (CLEAR, open-vocabulary) agrees; MedGemma alone invents masses and lines on normal films
    return [o for o in imaging.get("other_findings", []) if o.get("maps_to") not in known and o.get("verified", True)]


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
    print("reconcile ok", by)
