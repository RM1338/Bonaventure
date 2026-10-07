# Bonaventure demo library

Fictional patients; films from NIH ChestX-ray14 (Wang et al., CVPR 2017).

| Case | Film | NIH labels | Screening score |
|---|---|---|---|
| 01 Pleural effusion | 00002300_000 | Effusion | 0.994 |
| 02 Cardiomegaly | 00004344_013 | Cardiomegaly | 0.991 |
| 03 Pulmonary edema | 00006991_013 | Edema | 0.998 |
| 04 Pneumonia | 00003803_013 | Consolidation | 0.995 |
| 05 Atelectasis | 00002856_018 | Atelectasis | 0.888 |
| 06 Pneumothorax | 00001170_035 | Pneumothorax | 0.973 |
| 07 Lung mass | 00002046_005 | Mass | 0.985 |
| 08 Emphysema | 00006378_004 | Emphysema | 0.855 |
| 09 Pulmonary fibrosis | 00000218_005 | Fibrosis | 1.000 |
| 10 Pleural thickening | 00003072_020 | Pleural_Thickening | 0.977 |
| 11 Hiatus hernia | 00000284_003 | Hernia | 0.944 |
| 12 Lines and devices | 00006481_013 | Cardiomegaly, Fibrosis, Infiltration | 0.757 |
| 13 Normal | 00001456_001 | No Finding | -0.749 |
| 14 Pulmonary embolism (not on X-ray) | 00004808_070 | No Finding | -0.730 |

## What Bonaventure reports

| Case | Bonaventure case | Result |
|---|---|---|
| 01 Pleural effusion | BV-224 | Pleural effusion: SUPPORTED (high, image confidence 98 %); Consolidation: SUPPORTED (high, image confidence 84 %); Pleural thickening: SUPPORTED (high, image confidence 28 %); Atelectasis: SUPPORTED (moderate, image confidence 62 %); Cardiomegaly: SUPPORTED (high, image confidence 54 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 74 %) |
| 02 Cardiomegaly | BV-225 | Cardiomegaly: SUPPORTED (high, image confidence 96 %); Pulmonary edema: SUPPORTED (high, image confidence 82 %); Consolidation: SUPPORTED (high, image confidence 32 %) |
| 03 Pulmonary edema | BV-226 | Pulmonary edema: SUPPORTED (high, image confidence 94 %); Consolidation: SUPPORTED (high, image confidence 48 %); Cardiomegaly: SUPPORTED (high, image confidence 92 %); Atelectasis: UNCERTAIN (low, image confidence 49 %) |
| 04 Pneumonia | BV-227 | Pleural effusion: SUPPORTED (high, image confidence 98 %); Consolidation: SUPPORTED (high, image confidence 84 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 60 %); Atelectasis: UNCERTAIN (moderate, image confidence 66 %); Pleural thickening: UNCERTAIN (low, image confidence 38 %); Lines & devices: UNCERTAIN (moderate, image confidence 56 %); Cardiomegaly: UNCERTAIN (moderate, image confidence 79 %) |
| 05 Atelectasis | BV-228 | Atelectasis: SUPPORTED (high, image confidence 86 %); Widened mediastinum: CONFLICTING (low, image confidence 52 %) |
| 06 Pneumothorax | BV-229 | Cardiomegaly: SUPPORTED (high, image confidence 32 %); Lines & devices: UNCERTAIN (low, image confidence 38 %); Pneumothorax: UNCERTAIN (moderate, image confidence 53 %); Atelectasis: UNCERTAIN (moderate, image confidence 75 %); Pleural effusion: UNCERTAIN (moderate, image confidence 64 %) |
| 07 Lung mass | BV-230 | Widened mediastinum: CONFLICTING (low, image confidence 45 %); Consolidation: UNCERTAIN (moderate, image confidence 20 %); Lines & devices: UNCERTAIN (low, image confidence 32 %); Atelectasis: UNCERTAIN (moderate, image confidence 43 %); Also seen: Right upper lobe opacity; Also seen: Right lower lobe opacity |
| 08 Emphysema | BV-231 | Emphysema: SUPPORTED (high); Atelectasis: UNCERTAIN (moderate, image confidence 34 %) |
| 09 Pulmonary fibrosis | BV-232 | Pulmonary fibrosis: SUPPORTED (high); Cardiomegaly: SUPPORTED (high, image confidence 56 %); Consolidation: UNCERTAIN (moderate, image confidence 49 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 70 %) |
| 10 Pleural thickening | BV-233 | Pleural thickening: SUPPORTED (high, image confidence 44 %); Pleural effusion: SUPPORTED (high, image confidence 98 %); Atelectasis: SUPPORTED (high, image confidence 59 %); Cardiomegaly: SUPPORTED (high, image confidence 38 %); Consolidation: CONFLICTING (moderate, image confidence 54 %); Pulmonary edema: UNCERTAIN (low, image confidence 22 %); Also seen: Right lung opacity; Also seen: Elevated right hemidiaphragm |
| 11 Hiatus hernia | BV-234 | Hiatus hernia: SUPPORTED (high, image confidence 70 %); Cardiomegaly: SUPPORTED (high, image confidence 61 %); Pleural thickening: SUPPORTED (moderate, image confidence 25 %); Atelectasis: INSUFFICIENT_EVIDENCE (low, image confidence 30 %); Lines & devices: INSUFFICIENT_EVIDENCE (low, image confidence 38 %) |
| 12 Lines and devices | BV-235 | Cardiomegaly: UNCERTAIN (moderate, image confidence 96 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 64 %); Pleural effusion: UNCERTAIN (moderate, image confidence 58 %); Lines & devices: UNCERTAIN (moderate, image confidence 74 %); Atelectasis: UNCERTAIN (low, image confidence 44 %) |
| 13 Normal | BV-236 | No findings |
| 14 Pulmonary embolism (not on X-ray) | BV-237 | Not assessable on X-ray: Pulmonary embolism |
