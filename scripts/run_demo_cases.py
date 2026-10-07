"""Run the three acceptance demo cases (docs/11) end-to-end on the real models and print what each produced.

    PYTHONPATH=. .venv/bin/python scripts/run_demo_cases.py      # then: ./run.sh BV-xxx to open any of them
"""
import time

from bonaventure import imaging, pipeline

CASES = {
    "A · high agreement": ("kerley_b.jpg", ["case_a_history.pdf"],
                           "Worsening shortness of breath for 3 days, can't lie flat, waking up breathless at night, ankle swelling. No fever, no cough."),
    # same film as A, different patient context -> Bonaventure refuses to agree with the image alone
    "B · contradiction": ("kerley_b.jpg", ["case_b_history.pdf"],
                          "Breathless for 2 days. Denies fever, cough and ankle swelling."),
    "C · poor image": ("degraded_cxr.jpg", [], "Mild breathlessness."),
    # the film cannot answer the clinical question: Bonaventure must say so rather than force a finding
    "D · not on X-ray": ("Chest_Xray_PA_3-8-2010.png", ["case_d_history.pdf"],
                         "Sudden pleuritic chest pain and breathlessness since this morning, heart racing, right calf swelling."),
    # two records from two different patients: Bonaventure must refuse to reason with either
    "E · wrong patient": ("kerley_b.jpg", ["case_a_history.pdf", "case_b_history.pdf"],
                          "Short of breath for 3 days, can't lie flat."),
    # sanity checks: normal films should not grow findings
    "N · normal": ("Normal_posteroanterior_PA_chest_radiograph_X-ray.jpg", [], "Routine check, no symptoms."),
    "N2 · normal": ("Chest_Xray_PA_3-8-2010.png", [], "Pre-employment check."),
}

if __name__ == "__main__":
    import sys
    for extra in sys.argv[1:]:  # any extra films to try: run_demo_cases.py path/to/film.png ...
        CASES[f"extra · {extra.rsplit('/', 1)[-1]}"] = (extra, [], "")
    eng = imaging.ImagingEngine()
    while not eng.ready():
        time.sleep(0.5)
    print("engine", eng.status)
    for label, (scan, hist, symptoms) in CASES.items():
        c = pipeline.Case({"path": scan if "/" in scan else f"sample_data/scans/{scan}", "name": scan.rsplit("/", 1)[-1]},
                          [{"path": f"sample_data/histories/{h}", "name": h} for h in hist], symptoms)
        c.run(eng)
        r = c.result or {}
        if c.error: print(c.error["details"][-1500:])
        print(f"\n== Case {label}: {c.id} {c.state}  quality={r.get('quality', {}).get('state')}  t={r.get('technical', {}).get('total_seconds')}s")
        for f in r.get("findings", []):
            print(f"   {f['display_name']:<18} {f['status']:<22} {f['evidence_strength']:<9} img={f['signals']['image']}/{f['signals']['verifier']}"
                  f"  loc={'yes' if f['localization'] else 'no'}  {(f['contradictions'] + f['notes'])[:1]}")
        for o in r.get("other_observations", []):
            print(f"   + also seen: {o['name']} ({o.get('region')})  [{o['source']}]")
        if r.get("identity", {}).get("status") == "mismatch":
            print("   ! identity mismatch — history not used")
        for row in (r.get("interval") or {}).get("rows", []):
            print(f"   ~ since last report: {row['change']:<12} {row['finding']}  (prior: {row['prior_quote'][:50]})")
        if r.get("rejected"):
            print(f"   x rejected: {len(r['rejected'])} — " + "; ".join(x['claim'] for x in r['rejected'])[:120])
        for n in r.get("not_assessable", []):
            print(f"   ! not assessable on X-ray: {n['name']} — raised by {', '.join(n['because'])}")
