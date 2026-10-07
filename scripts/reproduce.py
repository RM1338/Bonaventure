"""Reproduce bundled demos without overwriting committed example results.

    .venv/bin/python scripts/reproduce.py --suite library --case 02 --pdf
    .venv/bin/python scripts/reproduce.py --suite acceptance --case A --case B
    .venv/bin/python scripts/reproduce.py --suite library --list

Real inference is the default. Mock mode must be explicitly requested and is
recorded in the manifest. Results go to cases/demo-runs/<timestamp>/.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REQUIRED_MODELS = ("primary", "verifier", "concepts", "reasoning", "segmentation")


def catalogue(suite):
    if suite == "library":
        rows = []
        for folder in sorted((ROOT / "demo_data").iterdir()):
            if folder.is_dir():
                rows.append(dict(key=folder.name.split()[0], label=folder.name,
                                 scan=folder / "film.png", histories=[folder / "history.pdf"],
                                 presentation=folder / "presentation.txt"))
        return rows
    from run_demo_cases import CASES
    return [dict(key=label.split(" ·")[0], label=label,
                 scan=ROOT / "sample_data/scans" / scan,
                 histories=[ROOT / "sample_data/histories" / name for name in histories],
                 text=text) for label, (scan, histories, text) in CASES.items()]


def select_cases(rows, requested):
    if not requested:
        return rows
    wanted = {key.upper().zfill(2) if key.isdigit() else key.upper() for key in requested}
    unknown = wanted - {row["key"] for row in rows}
    if unknown:
        raise ValueError("Unknown case(s): " + ", ".join(sorted(unknown)) + "; use --list")
    return [row for row in rows if row["key"] in wanted]


def inputs(row):
    return [row["scan"], *row["histories"], *([row["presentation"]] if "presentation" in row else [])]


def wait_for_models(engine, mock, timeout):
    deadline = time.monotonic() + timeout
    while not engine.ready():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Model loading exceeded {timeout:g}s")
        time.sleep(0.25)
    if mock:
        if not engine.mock:
            raise RuntimeError("Mock mode requested, but the engine did not enable it")
        return
    if engine.mock:
        raise RuntimeError("Real models failed to load; refusing automatic mock output")
    missing = [name for name in REQUIRED_MODELS if name not in engine.models]
    if missing:
        raise RuntimeError("Full demo requires these unavailable models: " + ", ".join(missing))


def fingerprint(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def environment():
    dirty = None
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                         stderr=subprocess.DEVNULL, timeout=5).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True,
                                            stderr=subprocess.DEVNULL, timeout=5).strip())
    except (OSError, subprocess.SubprocessError):
        commit = None
    packages = {}
    for name in ("torch", "torchvision", "transformers", "numpy", "weasyprint"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not installed"
    return dict(commit=commit, uncommitted_changes=dirty, platform=platform.platform(),
                python=sys.version.split()[0], packages=packages)


def run_case(row, engine, destination, export_pdf):
    from bonaventure import pipeline
    destination.mkdir()
    text = row["presentation"].read_text() if "presentation" in row else row["text"]
    entry = dict(key=row["key"], label=row["label"], inputs=[fingerprint(p) for p in inputs(row)],
                 presentation=text, state="FAILED")
    case = None
    try:
        case = pipeline.Case(dict(path=str(row["scan"]), name=row["scan"].name),
                             [dict(path=str(p), name=p.name) for p in row["histories"]], text)
        entry["case_id"] = case.id
        case.run(engine)
        (destination / "progress.json").write_text(json.dumps(case.progress(), indent=2))
        if case.error or case.result is None or case.state != "REVIEW_READY":
            raise RuntimeError(json.dumps(case.error or {"message": "Case produced no ready result"}))
        (destination / "result.json").write_text(json.dumps(case.result, indent=2))
        entry.update(state=case.state, reopen=f"./run.sh {case.id}",
                     findings=[dict(name=f["display_name"], status=f["status"],
                                    strength=f["evidence_strength"], confidence=f.get("confidence"))
                               for f in case.result.get("findings", [])],
                     not_assessable=[n["name"] for n in case.result.get("not_assessable", [])])
        if export_pdf:
            from bonaventure import report
            shutil.copy2(report.generate(case.result), destination / "report.pdf")
    except Exception as exc:
        entry.update(state="FAILED", error=str(exc))
        (destination / "error.json").write_text(json.dumps(entry, indent=2))
    print(f"{row['label']}: {entry.get('case_id', 'no case')} {entry['state']}", flush=True)
    for finding in entry.get("findings", []):
        print(f"  {finding['name']}: {finding['status']} ({finding['strength']})", flush=True)
    if entry.get("error"):
        print(f"  {entry['error']}", file=sys.stderr, flush=True)
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", choices=("library", "acceptance"), default="library")
    parser.add_argument("--case", action="append", help="case number (01–14), or A/B/C/D/E/N/N2; repeat to select several")
    parser.add_argument("--list", action="store_true", help="list cases without loading models")
    parser.add_argument("--check-inputs", action="store_true", help="check selected bundled files without inference")
    parser.add_argument("--mock", action="store_true", help="explicit synthetic UI/pipeline check, not real model evidence")
    parser.add_argument("--pdf", action="store_true", help="also generate a PDF for each successful case")
    parser.add_argument("--output", type=Path, help="new output directory; must not already exist")
    parser.add_argument("--load-timeout", type=float, default=1200, help="model loading limit in seconds")
    args = parser.parse_args(argv)
    if not math.isfinite(args.load_timeout) or args.load_timeout <= 0:
        parser.error("--load-timeout must be positive and finite")
    try:
        selected = select_cases(catalogue(args.suite), args.case)
    except ValueError as exc:
        parser.error(str(exc))
    if not selected:
        parser.error("No bundled cases found")
    if args.list:
        for row in selected:
            print(f"{row['key']}: {row['label']}")
        return 0
    missing = [str(p) for row in selected for p in inputs(row) if not p.is_file() or p.stat().st_size == 0]
    if missing:
        print("Missing/empty inputs:\n" + "\n".join(missing), file=sys.stderr)
        return 1
    if args.check_inputs:
        print(f"All inputs present for {len(selected)} {args.suite} case(s)")
        return 0
    if not args.mock and os.environ.get("BV_MOCK") == "1":
        parser.error("BV_MOCK=1 is set; unset it for real inference or explicitly pass --mock")
    if args.mock:
        os.environ["BV_MOCK"] = "1"
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or ROOT / "cases/demo-runs" / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(created=stamp, suite=args.suite, mode="mock" if args.mock else "real",
                    state="RUNNING", environment=environment(), cases=[])
    manifest_path = output / "manifest.json"

    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2))

    save()
    print(f"Mode: {manifest['mode']}; outputs: {output}", flush=True)
    try:
        from bonaventure.imaging import ImagingEngine
        engine = ImagingEngine()
        wait_for_models(engine, args.mock, args.load_timeout)
        manifest["model_status"] = engine.status
        for row in selected:
            manifest["cases"].append(run_case(row, engine, output / row["key"], args.pdf))
            save()
        manifest["state"] = "FAILED" if any(c["state"] == "FAILED" for c in manifest["cases"]) else "COMPLETE"
    except Exception as exc:
        manifest.update(state="FAILED", error=str(exc))
        print(str(exc), file=sys.stderr)
    save()
    print(f"{manifest['state']}: {manifest_path}", flush=True)
    return int(manifest["state"] != "COMPLETE")


if __name__ == "__main__":
    raise SystemExit(main())
