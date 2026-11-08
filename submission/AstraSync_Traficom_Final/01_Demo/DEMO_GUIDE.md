# Demonstration guide

**Recording status: PENDING.** No demonstration video has been recorded yet. This folder holds
the guide, the 3–5 minute script ([`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)) and the access
instructions ([`DEMO_ACCESS.md`](DEMO_ACCESS.md)) to record or run it live.

## Two ways to see AstraSync

| | Judge demonstration (`/demo`) | Full application (local) |
| --- | --- | --- |
| Data | **Synthetic** notices (administration `DEMO`, IDs `DEMO-…`), computed by the real code; every screen is bannered "Demonstration data (synthetic)" | **Real** ITU IFIC 3073/3074 and 3075/3076, live Traficom M4, challenge workbook |
| Sign-in | None; no API calls, no privileges | Development identity provider with test personas |
| Shows | Land-border and territorial-sea exceedance, coordinated notice, near-threshold, below threshold, workbook bandwidth mismatch, space PFD upper bound, missing satellite beam data | Everything below |

## Functionality available, and how it was verified

| # | Step | Where | Verified |
| --- | --- | --- | --- |
| 1 | Select or ingest IFIC input: check the ITU sources (discovery + download) or upload a file | Source library (`/sources`), Upload (`/uploads`) | Live run 2026-11-08: Space 3073/3074 and Terrestrial 3075/3076 downloaded, verified, parsed (0 records rejected) |
| 2 | Process notices: each indexed issue is analysed automatically by the worker | IFIC issues (`/ific`) | Live run: four analyses; results identical to the offline evaluation |
| 3 | Compare with Finnish frequency use (M4 + workbook stations) | Finding detail, stage A/B | Same live run; workbook parsed with organizer-clarified bandwidth rules |
| 4 | Inspect Space 3074 findings (PFD upper bounds, geometry, anomalies) | `/ific` → 3074 | Live run and committed outputs |
| 5 | Inspect Terrestrial 3076 findings (border and territorial-sea field strengths, threshold, margin, class) | `/ific` → 3076, criterion panel | Committed outputs; UI tests |
| 6 | Review calculations, thresholds, margins and evidence for a case | Cases (`/cases`) → Methods, Criteria, Evidence tabs | Live case analysed (P.1546 31.75 dB(µV/m)) |
| 7 | AstraSync Intelligence: grounded draft and "Ask" questions through local n8n → Ollama | Case → Draft and review, Ask | Live 2026-11-08 with `qwen3:8b`; needs local n8n and Ollama, otherwise the deterministic drafter is used |
| 8 | Export results: evidence pack per case; evaluation CSV/XLSX/JSON per issue | Case export; `ific_evaluate` command | Committed outputs in this package |

Not shown because not implemented: RR Article 21 PFD limit comparison, EPFD, terrain-aware
propagation (see [`../06_Technical_Documentation/LIMITATIONS.md`](../06_Technical_Documentation/LIMITATIONS.md)).
