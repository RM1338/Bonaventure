# Bonaventure — Project Documentation

Bonaventure is a clinician-facing chest X-ray evidence reconciliation assistant designed for **HackNex 2026 Internal Qualifier — HNX26PSI05: Multimodal Medical Image Intelligence**.

This documentation set is organized to support implementation, evaluation, team coordination, and the final public repository.

## Running the current application

See the [repository README](../README.md) for current installation commands,
[platform selection](../README.md#desktop-platforms),
[shared model layout](../README.md#models-both-platforms),
[macOS setup and background startup](../README.md#install-macos), and
[launch commands](../README.md#run).

`./run.sh` selects the original Linux desktop (`bonaventure/linux_app.py` and
`bonaventure/ui/island_linux.html`) on Linux, and the edited notch desktop
(`bonaventure/macos_app.py` and `bonaventure/ui/island.html`) on macOS. Linux never
imports the macOS desktop implementation or loads its launcher HTML.
The notch panel, menu bar icon, Option + Command + B shortcut, hover activation,
and app/login installer apply only to macOS. Linux keeps its original pill,
Hyprland integration, and optional toggle-script shortcut/bar configuration.

The reading room, inference pipeline, reports, and model setup are shared.
Put model assets directly under `models/`, not `models/Models/`, and run
`.venv/bin/python scripts/check_setup.py` before real inference. Use
`BV_MOCK=1 BV_START=expand ./run.sh` for a UI demo without model loading.
The setup checker verifies dependencies and file presence; native GUI behavior
and successful model inference require separate runtime checks on each platform.
The original Linux runtime was tested on Arch/Omarchy with Hyprland; other
distros and desktop environments are not confirmed by that result.

The numbered documents below contain product specifications and implementation
plans. Use the repository README for the current executable file layout and
platform-specific operating instructions.

## Documentation Index

1. `01_PRD.md` — Product Requirements Document
2. `02_SRS.md` — Software Requirements Specification
3. `03_SYSTEM_ARCHITECTURE.md` — High-level and component architecture
4. `04_AI_PIPELINE.md` — Medical AI and evidence-reconciliation pipeline
5. `05_DATA_AND_EVALUATION.md` — Datasets, metrics, validation, robustness
6. `06_API_CONTRACTS.md` — Internal API and JSON contracts
7. `07_UI_UX_SPEC.md` — Quick-launcher and clinical review workspace UX
8. `08_REPORT_SPEC.md` — Clinician-facing PDF report specification
9. `09_IMPLEMENTATION_PLAN.md` — Team split, milestones, dependency plan
10. `10_TEST_PLAN.md` — Functional, model, robustness, and demo testing
11. `11_DEMO_AND_ACCEPTANCE.md` — Demo script and acceptance criteria
12. `12_RISK_REGISTER.md` — Technical, medical, data, and demo risks
13. `13_MODEL_RESOURCE_REGISTER.md` — External models/resources declaration template
14. `14_PS_TRACEABILITY_MATRIX.md` — Mapping from HackNex PS requirements to Bonaventure
15. `15_REPOSITORY_STRUCTURE.md` — Recommended implementation layout

## Product Definition

> **Bonaventure — Clinical Evidence Intelligence**  
> A clinician-facing chest X-ray evidence reconciliation assistant that combines current imaging, longitudinal patient history, and current symptoms to produce localized, uncertainty-aware findings for clinician review.

## Core Principle

Bonaventure is a **decision-support tool**, not an autonomous diagnostic system.

Every displayed finding must be backed by image evidence and/or patient-context evidence, and uncertainty or disagreement must be surfaced rather than hidden.
