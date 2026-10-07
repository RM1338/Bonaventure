# macOS PR review and integration

Reviewed [PR #4](https://github.com/RM1338/Bonaventure/pull/4), authored by
Gavriel Stephen Elijah (`gavriel953`), at original head
`ad8c2c3e0909e51cd303d32d0dc9bdb5190b021d` on 2026-10-07.
Integrated current main `769bdad` into that same branch. No replacement PR was
created and no original commit was squashed or re-authored.

## Setup comparison with PR #7 and the Omarchy machine

Compared Gavriel's [macOS guide PR #7](https://github.com/RM1338/Bonaventure/pull/7)
at `076320f5ac29bba8f56e48919c31dc246e5e4397` with the current instructions.
The Mac setup now uses that guide's exact Homebrew package list, explicit
`$(brew --prefix python@3.12)/bin/python3.12` interpreter, virtual-environment
pip workflow, repo-local model folders, filtered downloads and DINOv2 cache
preparation. The only dependency-file adaptation is `requirements-macos.txt`,
whose active package pins match the guide's original requirements on Darwin.
The guide's older documentation-branch clone is replaced by the updated PR #4
branch, which also contains current main and the reproduction runner.

Linux instructions follow the original README at `769bdad`: Arch packages,
`uv venv --python /usr/bin/python3 --system-site-packages`, CUDA 12.8 wheels and
the original home/top-level model layout. The local `pyvenv.cfg` confirms uv
0.12.22, Python 3.14.7 and system-site-packages; installed torch/torchvision are
2.11.0+cu128 and 0.26.0+cu128. Package logs and shell history confirm native
dependencies, but do not record every virtual-environment installation command;
the command sequence is sourced from the original project documentation. The
Linux entry point includes the same active package pins as those original
requirements, including bitsandbytes. No environment or installed package was
changed by this documentation follow-up.

Both platform-specific dependency sets match their source after evaluating OS
markers. All 15 current README bash blocks pass syntax checks; the local
dependency/Whisper/recorder check passes. Native installation on a new Mac has
not been executed here. During the setup comparison, PR #7 was used as a reference. Its later merge
preserves the complete guide in `MACOS_SETUP.md`, correcting outdated clone and
reference-result details while keeping the current README.

## Findings and fixes

| Finding | Evidence | Resolution |
|---|---|---|
| PR targets an older platform branch, while main has newer evidence code and removes the Mac shell | A three-way merge conflicts in the READMEs and modified Mac files; other unchanged Mac helpers/tests would be deleted automatically | Preserve Gavriel's Mac routing, shell, helpers, installer and tests; retain main's calibrated confidence, heatmap, rejected-claim rules, demo assets and diagrams. Target the existing PR at main |
| Mac README incorrectly says MPS is disabled | `model_runtime.medgemma_device` selects MPS on supported Macs, and `load_medgemma` chooses bfloat16/float32 | README now describes CUDA, MPS and CPU behavior and their different memory/timing requirements |
| Installation uses one requirements entry point, with Linux-specific guidance | Linux needs CUDA wheels, bitsandbytes, WebKitGTK/GTK and PipeWire; macOS needs standard torch wheels, PyObjC, Homebrew Pango/Poppler and ffmpeg | Shared pinned versions remain in `requirements.txt`; separate `requirements-linux.txt` and `requirements-macos.txt` and complete OS commands are documented |
| Homebrew Pango may not be discoverable when launching the installed Mac app | `run.sh` previously only configured Linux graphics paths | The Darwin launch path sets `DYLD_FALLBACK_LIBRARY_PATH` from the installed Homebrew prefix; Linux retains its existing WebKit/Mesa setup |
| Fresh clones lack explicit checkpoint acquisition and initialization steps | Cloning CheXzero/MedSAM does not download their weights; CLEAR's DINOv2 loader needs a code cache | README includes official checkpoint folders, exact destination filenames, CLEAR patch/DINOv2 cache preparation, and gated MedGemma download steps |
| Demo scripts are unsuitable as the sole reproducibility entry point | The library runner rewrites committed result summaries; legacy runners do not reliably signal failed analysis with nonzero exit; neither offers case selection and a run manifest | Add `scripts/reproduce.py` with selected/all library or acceptance cases, input checks, SHA-256 provenance, fresh JSON/progress/PDF outputs and nonzero failure exits. Real runs require all models and reject automatic mock fallback |
| Saved BV IDs in examples are machine-specific | `cases/` is excluded from Git | README tells evaluators to use the newly generated case ID, with commands for reopening it |

## Automated verification

The original PR passed **99 Python tests** and **three JavaScript test files**.
After integration and reproduction changes, **106 Python tests** and the same
three JavaScript test files pass. Context/reconciliation self-tests, model-output
parsing checks, Python syntax and shell syntax pass. Both bundled suites have all
their inputs: 14 library cases and seven acceptance cases.

The seven additional regression tests cover automatic mock rejection, missing
models, loading timeouts, invalid selection, deduplication, failed analysis and
PDF-export failure. Failures remain failures instead of being presented as an
empty successful result. A separate explicitly mocked run of library case 02
generated JSON, stage progress, a manifest and a valid three-page PDF.

A **real Linux/CUDA run** of library case 02 then completed in 32.56 seconds of
pipeline time (excluding initial model loading), with all required models loaded.
It generated a valid four-page PDF. Its image confidence values matched the
committed reference: cardiomegaly 96%, pulmonary edema 82%, consolidation 32%.
All three had localization and occlusion heatmaps, and 10 claims were rejected.
Consolidation's high rule-based evidence strength alongside low image confidence
is an existing documented limitation, not a claim of validated diagnosis. This
run does not verify MPS or native Mac UI behavior.

Full reproduction commands and expected acceptance outcomes are in the
[README](../README.md#reproduce-the-demonstrated-results). No committed demo
input or reference result was overwritten during these checks.

## Remaining native verification

This review runs on Linux. Fake native APIs exercise Mac control logic, but
passing those tests does not establish that the actual Mac GUI or MPS backend
works correctly. On the teammate's Mac, verify:

1. OS-specific install and setup checks, then mock launch for notch/menu-bar
   placement, picker order and selection/cancellation.
2. Option–Command–B, hover, hide/reopen while processing, ready/review reopening.
3. Microphone permission, real Whisper live captions, stop/final transcript and
   repeated recording from the installed app.
4. A real case 02 run with a fresh PDF. Confirm the logged MedGemma device/dtype;
   retain its manifest and result, rather than assuming RTX timings apply.
5. Finder/login startup and PDF viewer opening.

Detailed steps are in [DESKTOP_VERIFICATION.md](DESKTOP_VERIFICATION.md).

## Contributor attribution

Keep Gavriel's original commits when merging this PR into the default branch.
A normal merge preserves their authorship. GitHub's contributor graph requires
commits in the default branch and an author email linked to the account;
an open PR alone is insufficient ([GitHub documentation](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-a-projects-contributors)).
