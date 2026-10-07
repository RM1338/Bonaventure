# Desktop verification

Verification snapshot for `feat/macos-picker-startup-fixes` (2026-10-07).
The test environment is Linux. The mounted `.venv` points to a Homebrew macOS
interpreter and cannot execute here. Native Mac results remain unverified.

## Automated results

All **63 Python tests** and the Node launcher checks pass. Context and evidence
reconciliation self-checks also pass. These tests use fake native APIs, clocks,
recorders, and speech decoders where the real platform or models are unavailable.

| Requested behavior | Evidence | Remaining native check |
|---|---|---|
| Separate Linux and Mac launchers | Dispatcher import tests; separate Linux/Mac shells; shared dictation handler and API lifecycle updated on both platforms | Run each GUI on its OS |
| Full notch coverage and controls below camera | Safe-area/auxiliary-area geometry; screen offsets and selected displays | Check the actual camera cutout, menu bar, Spaces, and fullscreen |
| Black notch cap with subtle progress-card tint | Mac markup/style review; original Linux stylesheet untouched | Judge rendered appearance |
| Shortcut from another application | Carbon registration, event-ID filtering, conflict handling; controller toggles | Deliver Option–Command–B while another app is active |
| Hover activation and dismissal | Dwell, leave grace, pinning, explicit-hide suppression, processing protection; controller event tests | Verify mouse events on the Mac |
| Closing transition and flicker | Actual-animation completion/cancellation, final paint, stable native frame, delayed focus release, reduced motion | Watch the menu bar while repeatedly closing; automated tests cannot establish flicker is gone |
| Foreground file selection | Window levels, multi/single selection, cancellation, retries, duplicate clicks, errors, cleanup failure recovery, controller pause | Open/select/cancel native picker; verify it stays in front |
| Background and login startup | Wrapper execution with spaces, minimal login PATH, microphone plist; mocked install/no-login/uninstall/running-instance flows | Finder launch, login launch, microphone permission |
| Progress redesign | Stage index, skipped/completed stages, grouped phases, review-ready and reset states | Render real analysis progress |
| Input preservation | Draft inputs and processing view survive hide/reopen; rapid-toggle races | Verify scan/history attachments with native picker |
| Voice model locations | Repo/home lookup and environment overrides; optional setup checks | Load and decode with the real speech models |
| Voice recording lifecycle | Final/live decoder fallback, typed-text preservation, live captions, final replacement, cancellation, saved WAV, recorder exit race, kill/reap, pending start/stop, serialized restart, stale captions, quit cleanup | Real microphone capture and Whisper decoding |
| Local imaging setup | Existing source/config/checkpoint file-presence checks pass | Load weights and run inference |

Python syntax, shell syntax, README links/anchors, and `git diff --check` pass.
The imaging setup checker finds the local CLEAR, CheXzero, MedSAM, and MedGemma
assets. Its dependency checks fail under the bare Linux test interpreter, which
does not have the Mac application's packages. This does not establish a problem
with the user's Mac virtual environment.

Both Whisper checkpoints are now present in the user's model folders, and the
user's Mac logs show model loading. The microphone start/stop regression is
covered with delayed UI bridge responses and mocked recorder/decoder tests;
real microphone capture and decoding still require the native runtime check.
Model download commands are in the
[repository README](../README.md#voice-dictation-optional-offline-english).

## Reproduce automated checks

From the repository root with your working virtual environment and Node:

```bash
.venv/bin/python -m unittest discover -s tests -v
node tests/island_state.test.cjs
node tests/dictation_state.test.cjs
.venv/bin/python -m bonaventure.context
.venv/bin/python -m bonaventure.reconcile
.venv/bin/python scripts/check_setup.py
.venv/bin/python scripts/check_setup.py --mock --voice
git diff --check
bash -n run.sh scripts/bonaventure-toggle
```

The voice setup command requires the optional voice downloads. A setup check
does not load models or verify checkpoint contents, rendering, or permissions.

## Mac runtime checks

Quit an existing instance completely before testing this branch.

```bash
BV_MOCK=1 BV_DEBUG=1 BV_START=expand ./run.sh
```

1. Inspect notch coverage and the black cap. Check placement on an external
   monitor as well, if available.
2. Switch to another app. Use Option–Command–B to open/close the launcher. Try
   the menu bar action and hovering below the notch, including a brief pass
   that should not open it.
3. Click/type inside the launcher and move away: it should remain open. Close
   with Escape or its button. Repeat and rapidly toggle; watch the menu bar for
   a flash/jump. Enable Reduce Motion and repeat.
4. Click Chest X-ray. The picker should appear in front. Cancel it, reopen it,
   choose an image, and repeat with multiple history files. Verify repeated
   clicks do not open duplicate pickers or leave the launcher stuck.
5. Keep typed presentation text and attachments while hiding/reopening. Run a
   mock analysis to inspect progress and confirm the reading room opens. Close
   the reading room and start a new case.
6. After the Whisper downloads, test microphone start, live captions, stop,
   final text, and another recording. Test denied microphone permission as
   well; do not count a mock decoder test as a successful voice run.
7. Quit the app, then run `.venv/bin/python scripts/install_macos.py`. Test
   background controls without Terminal, quit/reopen from Finder, and verify
   startup at the next login. Recheck dictation from the installed app.
8. For real imaging, quit the demo and run `BV_START=expand ./run.sh`. Verify
   scan analysis, evidence review, and PDF export with the intended local
   weights; a mock run does not establish real inference works.

Background logs: `~/Library/Logs/Bonaventure/bonaventure.log`.

## Linux runtime checks

Use a Linux-native `.venv` with GTK dependencies. `BV_MOCK=1 BV_START=expand
./run.sh` should open the Linux pill/interface, with the friend's latest Linux
features, without loading Mac launcher code. Test its file picker, resize and
toggle behavior in the intended desktop environment. No Linux graphical session
was exercised by this verification snapshot.
