# macOS branch audit

Branch policy: `main` is the Omarchy/Linux release; `macos` is the Mac desktop.
This audit and fix branch is based on `macos`. No changes target `main`.

## Issues corrected

- The Mac branch's entry point previously selected Linux/Windows shells as well.
  It now rejects non-Mac execution before importing native GUI libraries. Those
  machines receive a branch-selection message, rather than an AppKit/GTK error.
- Setup documentation incorrectly described the Mac implementation as being on
  `main`. The guide now clones `--branch macos`, and the README identifies the
  platform policy prominently. Historical platform instructions remain present.
- The installed Finder/login wrapper called Python directly, bypassing `run.sh`.
  It missed Homebrew Pango discovery and offline model flags. The wrapper and
  installer dependency preflight now both use the same launch script as Terminal.
- The launch script sets Homebrew executable paths, library paths, offline flags
  and unbuffered logs, reports a missing virtual environment clearly, and offers
  `--check-runtime` to verify native imports without opening the application.
- The Mac setup guide's private-repository warning was outdated. GitHub reports
  the repository as public; the guide tells evaluators to select `macos`.

- Explicit mock inference could crash when a randomly selected finding had no
  demo bounding box. It now retains that synthetic finding without inventing an
  outline. Real inference paths are unchanged.

## Validation

All **118 Python tests**, all **three Node UI suites**, context/reconciliation
self-checks, shell syntax and `git diff --check` pass. New launch tests execute the
actual shell script and installed wrapper with fake Darwin/Homebrew/Python
executables, including paths with spaces and shell metacharacters. They verify
consistent environment settings, preflight imports, Linux rejection, and the
missing-venv message. All seven acceptance and 14 library cases also complete in explicit mock mode;
input checks pass for all 21. This verifies orchestration, not real model accuracy
or PDF export. Existing picker, controls, hide/reopen, export, model
configuration, dictation and reproduction regressions pass.

The runner is Linux. NumPy/Pillow/pypdf for the dependency-light tests were
installed separately under `/tmp`; the Mac project's `.venv` was not changed.
Simulated platform tests do not verify native AppKit rendering, microphone
permissions, launchctl behavior, PDF viewer activation or real MPS inference.
No statement that those checks passed is implied by this audit.

## Apply and verify on the Mac

After the fix is merged into `macos`, quit the old application completely before
switching/updating the checkout. Keep the existing working Mac virtual environment
and model downloads.

```bash
git switch macos
git pull --ff-only origin macos
.venv/bin/python -m pip install -r requirements-macos.txt
./run.sh --check-runtime
.venv/bin/python scripts/check_setup.py
BV_START=expand ./run.sh
```

Confirm notch placement and the centered hide arrow, Option–Command–B, menu-bar
opening, hover behavior, foreground file selection, and hide/reopen during a case.
Run a real bundled case, inspect nonempty MedGemma raw image output and sources,
and export the PDF to verify the default viewer opens. If dictation is installed,
confirm start/stop and final transcription on the actual microphone.

Quit the Terminal-owned instance before replacing the old background wrapper:

```bash
.venv/bin/python scripts/install_macos.py
```

Verify Finder reopening and login startup; inspect
`~/Library/Logs/Bonaventure/bonaventure.log` for model device/dtype and stage logs.
Terminal and the installed wrapper now use the same runtime configuration.
Do not install this wrapper from a checkout switched back to Omarchy's `main`.
