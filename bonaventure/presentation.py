"""Optional clinical paraphrases must not prevent rule-based symptom parsing."""


def clinical_rewrites(engine, clauses, recognised):
    rewrites = [""] * len(clauses)
    pending = [i for i, clause in enumerate(clauses) if not recognised(clause)]
    if not pending:
        return rewrites, "", []
    model = None if engine.mock or not engine.ready() else engine.models.get("reasoning")
    if model is None:
        return rewrites, "", ["Clinical rewrite unavailable; original wording used. Unmatched phrases need review."]
    # Bound both model input and output. Never drop the original phrases.
    selected = [i for i in pending if len(clauses[i]) <= 500][:12]
    warnings = []
    if len(pending) > len(selected):
        warnings.append("Clinical rewrite limited to 12 unmatched phrases of at most 500 characters; remaining original phrases need review.")
    if not selected:
        return rewrites, "", warnings
    if not engine._lock.acquire(timeout=2):
        return rewrites, "", warnings + ["Clinical rewrite busy; original wording used. Unmatched phrases need review."]
    try:
        values, raw = model.rewrite_clinical([clauses[i] for i in selected])
        if len(values) != len(selected):
            raise ValueError("clinical rewrite returned the wrong number of phrases")
        for i, value in zip(selected, values):
            rewrites[i] = value
        return rewrites, raw, warnings
    except Exception as exc:
        print(f"[presentation] clinical rewrite unavailable: {exc!r}", flush=True)
        return rewrites, "", warnings + ["Clinical rewrite failed or exceeded its generation budget; original wording used. Unmatched phrases need review."]
    finally:
        engine._lock.release()
