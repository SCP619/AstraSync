# AstraSync — Traficom challenge submission

Since AI 2026, Traficom: **"Saving Earth from Space Interferers Using Radio Frequencies."**
Code baseline: GitHub `SCP619/AstraSync`, branch `main`, commit
`8e0f10535850d604911c430a8dc640ea960c925a` (the evaluation outputs here were produced by and
re-verified against this commit).

## What AstraSync does

AstraSync downloads ITU BR IFIC publications from the ITU website, parses the real notice
databases, compares every notice with Finnish frequency use (Traficom M4 table and the challenge
"frequencies of interest" workbook), runs reproducible RF calculations, and turns the results into
ranked, evidence-linked findings and cases that an expert can review, ask questions about and
draft correspondence from. Every number carries its inputs, assumptions, method version and hash.

- **Space:** Space IFIC (SNS v10 database) → per-group frequency matching → GSO/NGSO visibility of
  Finland → free-space PFD upper bound with worst-case (peak) beam gain over a 500-node Finland
  grid → prioritised findings.
- **Terrestrial (side quest):** Terrestrial BR IFIC (MDB extract) → change detection against the
  previous issue → land-mobile notices → ITU-R P.1546-6 field strength along Finland's land
  borders and the outer limit of its territorial sea → comparison with the ECC T/R 25-08 A1.2.3
  coordination thresholds → classified cases.

## Where to look

| Deliverable (organizers' list) | Location | Status |
| --- | --- | --- |
| 1. Demo of the solution | [`01_Demo/`](01_Demo/DEMO_GUIDE.md) | Guide, 3–5 min script and access instructions ready; **video recording pending** |
| 2. Ability to process IFIC files with Finnish usage information | [`04_Input_Output/PROCESSING_PIPELINE.md`](04_Input_Output/PROCESSING_PIPELINE.md), [`REPRODUCIBILITY.md`](04_Input_Output/REPRODUCIBILITY.md) | Implemented; one command per issue; re-run on 2026-11-08 reproduced the committed outputs |
| 3. Processed Space IFIC 3074 | [`02_Space_IFIC_3074/`](02_Space_IFIC_3074/SPACE_RESULTS_SUMMARY.md) | Real data, complete screening; **no approved space PFD limit**, so no margins |
| 3. Processed Terrestrial IFIC 3076 | [`03_Terrestrial_IFIC_3076/`](03_Terrestrial_IFIC_3076/TERRESTRIAL_RESULTS_SUMMARY.md) | Real data; thresholds and margins against ECC T/R 25-08 A1.2.3 |
| 4. Input/output information | [`04_Input_Output/`](04_Input_Output/INPUT_OUTPUT_GUIDE.md) | Complete, with one worked example per domain |
| 5. Code repository | [`05_Code_Repository/REPOSITORY_LINK.md`](05_Code_Repository/REPOSITORY_LINK.md) | Private GitHub repository; access to be granted to the evaluators |
| 6. Clarifying documentation | [`06_Technical_Documentation/`](06_Technical_Documentation/) | Validation, regulation, AI workflow, security, tests, limitations |

Machine-readable inventory with SHA-256 checksums: [`SUBMISSION_MANIFEST.json`](SUBMISSION_MANIFEST.json).
The checksums are of the files as packed in `AstraSync_Traficom_Final_Submission.zip`; a Git
checkout on Windows may convert line endings in text files.

## Headline results (real data)

- **Space IFIC 3074** (published 23.06.2026): 196 notices, 34,365 frequency groups, all screened.
  1 HIGH (D, SOLAR SENTRY: new NGSO system whose service area includes Finland), 111 MEDIUM,
  45 screened out because they cannot be seen from Finland, 33 with insufficient data. One
  impossible value in the published data flagged for clarification (IND LVI, `pwr_ds_max`
  +73 dBW/Hz).
- **Terrestrial IFIC 3076** (published 21.07.2026): 1,867 land-mobile notices. **6 exceed the
  ECC T/R 25-08 coordination threshold** at the Finland–Russia land border (Russian base stations
  near 152–153 MHz at Kostomuksha, Lyaskelya and Vyborg; margins +8.1 to +14.8 dB): 1
  `VERIFIED_CRITERION_EXCEEDANCE` and 5 `COORDINATION_REVIEW` (Finland already named in the
  coordination data). 42 below threshold, 534 frequency overlap only, 1,285 with insufficient
  evidence for a border calculation.

An exceedance of the indicative T/R 25-08 threshold means coordination with Finland is indicated.
It is **not** a finding of harmful interference or non-compliance.

## Mapping to the judging criteria

| Criterion | Where to look |
| --- | --- |
| A. Technical analysis and reproducibility (25 %) | `06_Technical_Documentation/SCIENTIFIC_VALIDATION.md`, `04_Input_Output/REPRODUCIBILITY.md`, each `manifest.json` |
| B. Extensibility and terrestrial side quest (25 %) | `05_Code_Repository/ARCHITECTURE.md`, `03_Terrestrial_IFIC_3076/` |
| C. Workflow usefulness and output quality (20 %) | `01_Demo/`, the ranked `findings.csv`/XLSX, `06_Technical_Documentation/AI_WORKFLOW.md` |
| D. Case recognition accuracy (15 %) | `03_Terrestrial_IFIC_3076/TERRESTRIAL_RESULTS_SUMMARY.md`, `02_Space_IFIC_3074/SPACE_RESULTS_SUMMARY.md` |
| E. Auditability and evidence quality (15 %) | `04_Input_Output/INPUT_OUTPUT_GUIDE.md` (worked examples), `06_Technical_Documentation/REGULATORY_REFERENCES.md`, calculation hashes in the JSON outputs |

## Run the demo

- No installation: the **judge demonstration** at `/demo` of the web UI, synthetic data computed by
  the real code, no sign-in ([`01_Demo/DEMO_ACCESS.md`](01_Demo/DEMO_ACCESS.md)).
- Full application with the real data: start the local stack and follow
  [`01_Demo/DEMO_SCRIPT.md`](01_Demo/DEMO_SCRIPT.md).

## Reproduce

See [`04_Input_Output/REPRODUCIBILITY.md`](04_Input_Output/REPRODUCIBILITY.md): download the four public
inputs (URLs and SHA-256 in each `manifest.json`), use the challenge workbook, run
`python -m astrasync_data.ific_evaluate space|terrestrial …`.

## What is verified and what is not

Verified: parsing and reconciliation of 3074 and 3076 against ITU's own counts; P.1546-6 port
(54/54 ITU-R WP 3K reference cases within 5.1×10⁻⁵ dB); T/R 25-08 threshold values read from the
6 June 2025 edition; reproducibility of both evaluations; CI on the baseline commit (backend on
SQLite and PostgreSQL, core, UI, Windows and Android builds, dependency and secret scans); live
local AI (n8n → Ollama) with grounding checks.

Not complete: no RR Article 21 PFD limit is applied (the complete authoritative Table 21-4 was not
obtained), so space results are ranked screenings without margins; no terrain database (heff = ha);
no EPFD or antenna-pattern modelling; special-interest stations are synthetic challenge data.
Full list: [`06_Technical_Documentation/LIMITATIONS.md`](06_Technical_Documentation/LIMITATIONS.md).
