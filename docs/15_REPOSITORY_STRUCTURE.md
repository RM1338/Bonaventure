# Recommended Repository Structure

```text
bonaventure/
│
├── apps/
│   └── desktop/
│       ├── launcher/
│       ├── review/
│       └── components/
│
├── backend/
│   ├── api/
│   ├── orchestrator/
│   ├── schemas/
│   └── services/
│
├── ai/
│   ├── imaging/
│   │   ├── preprocessing/
│   │   ├── primary_model/
│   │   ├── verifier/
│   │   └── localization/
│   │
│   ├── history/
│   │   ├── extraction/
│   │   ├── entities/
│   │   ├── timeline/
│   │   └── provenance/
│   │
│   ├── symptoms/
│   └── reconciliation/
│
├── reports/
│   ├── generator/
│   ├── templates/
│   └── assets/
│
├── evaluation/
│   ├── cases/
│   ├── expected/
│   ├── actual/
│   ├── metrics/
│   └── robustness/
│
├── sample_data/
│   ├── scans/
│   ├── histories/
│   └── symptoms/
│
├── docs/
│   ├── PRD.md
│   ├── SRS.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── AI_PIPELINE.md
│   ├── DATA_AND_EVALUATION.md
│   ├── API_CONTRACTS.md
│   ├── UI_UX_SPEC.md
│   ├── REPORT_SPEC.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── TEST_PLAN.md
│   ├── DEMO_AND_ACCEPTANCE.md
│   ├── RISK_REGISTER.md
│   ├── MODEL_RESOURCE_REGISTER.md
│   └── PS_TRACEABILITY_MATRIX.md
│
├── scripts/
│   ├── setup/
│   ├── download_models/
│   └── run_demo/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── demo/
│
├── .env.example
├── requirements.txt
├── LICENSE
└── README.md
```

## Branches

Suggested:
- `main`
- `dev`
- `feature/image-pipeline`
- `feature/history-pipeline`
- `feature/reconciliation`
- `feature/ui`
- `feature/report`

## Repository Rule

The public README must explain:
- what Bonaventure does,
- technologies/models used,
- installation,
- configuration,
- running,
- reproducing demonstrated results,
- external resources,
- MVP vs stretch scope.
