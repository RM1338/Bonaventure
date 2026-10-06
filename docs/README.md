# Bonaventure — Project Documentation

Bonaventure is a clinician-facing chest X-ray evidence reconciliation assistant designed for **HackNex 2026 Internal Qualifier — HNX26PSI05: Multimodal Medical Image Intelligence**.

This documentation set is organized to support implementation, evaluation, team coordination, and the final public repository.

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
