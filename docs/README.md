# Bonaventure — Project Documentation

Bonaventure is a clinician-facing chest X-ray evidence reconciliation assistant designed for **HackNex 2026 Internal Qualifier — HNX26PSI05: Multimodal Medical Image Intelligence**.

This documentation set is organized to support implementation, evaluation, team coordination, and the final public repository.

## Start here (as built)

* [`ARCHITECTURE.md`](ARCHITECTURE.md): the system as implemented, with component, data-pipeline, model and reconciliation diagrams
* [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md): a step-by-step walkthrough of one real case from input to report, plus likely judge questions
* [`PS05_CHECKLIST.md`](PS05_CHECKLIST.md): every PS05 requirement and submission guideline, mapped to where it is met
* [`sample_output/`](sample_output/): real outputs of demo cases A–E and a normal film (result JSON, PDF report, annotated film)
* [`13_MODEL_RESOURCE_REGISTER.md`](13_MODEL_RESOURCE_REGISTER.md): every external model, dataset and library
* [`DESKTOP_VERIFICATION.md`](DESKTOP_VERIFICATION.md): desktop regressions and native macOS/Linux checks
* [`MACOS_SETUP.md`](MACOS_SETUP.md): Gavriel’s complete Mac setup, troubleshooting and evaluation guide
* [`DIAGRAM_NOTES.md`](DIAGRAM_NOTES.md): platform scope and current processing details for the Lucidchart figures
* [`WINDOWS_SETUP.md`](WINDOWS_SETUP.md): Windows setup, recorded dependencies and native UI verification
* [`MACOS_PR_REVIEW.md`](MACOS_PR_REVIEW.md): review and integration of Gavriel's existing macOS PR

## Planning documents (written before implementation)

These were written before the build. Where they differ from the code, `ARCHITECTURE.md` is authoritative.


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
