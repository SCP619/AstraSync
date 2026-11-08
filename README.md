![AstraSync Logo](docs/assets/astrasync-logo.jpeg)

# AstraSync

Spectrum screening for the Finnish Transport and Communications Agency (Traficom).
Built for the Since AI 2026 Traficom challenge, "Saving Earth from Space Interferers Using Radio Frequencies".

## The problem

Every two weeks the ITU publishes the BR IFIC: thousands of new and changed satellite and terrestrial
frequency notices from administrations worldwide. Traficom must find the few that could affect radio use in
Finland, check them against the applicable criteria, and respond to the notifying administration in time.
Doing this by hand is slow, inconsistent and hard to audit.

## What AstraSync does

- **Acquires and parses** ITU Space IFIC (SNS) and Terrestrial BR IFIC issues, verifying SHA-256 and
  reconciling counts with the ITU ReadMe.
- **Screens relevance to Finland**: frequency overlap with the Traficom M4 allocation table and the
  challenge's frequencies-of-interest workbook (with bandwidth-mismatch and licence-class normalization),
  service match, geography and change detection against the previous issue.
- **Terrestrial (IFIC 3076)**: ITU-R P.1546-6 field strength (validated on 54 ITU reference cases) along
  Finland's land borders and territorial-sea outer limit, compared with ECC T/R 25-08 A1.2.3 coordination
  thresholds (applied above 470 MHz as an organizer-approved extension).
- **Space (IFIC 3074)**: worst-case free-space PFD over a 500-point Finland grid (GSO) or reachable
  elevations (NGSO), compared with ITU Radio Regulations Article 21 Table 21-4 (Edition of 2024).
- **Cases and evidence**: reviewable cases with provenance, append-only expert review, evidence export.
- **AI assistance on your own machine**: drafts and answers to questions about a case, produced by a local
  model (Ollama via n8n), grounded in case evidence; citations and numbers are checked server-side.
- **Security**: OIDC sign-in, deny-by-default authorization, tenant isolation, classification and
  source entitlements on every request.

Results are screening results for expert review, never findings of harmful interference or non-compliance.

## Results

Separate evaluation outputs for the two challenge issues: [`evaluation/`](evaluation/README.md)
(CSV, XLSX, JSON, Markdown reports with full provenance).

## Using AstraSync

### Web / Windows desktop

1. Set up the PC: [`docs/WINDOWS_DEVELOPMENT_SETUP.md`](docs/WINDOWS_DEVELOPMENT_SETUP.md).
2. Start the backend: `traficom-integration\backend\.venv\Scripts\python traficom-integration\backend\tests\support\dev_stack.py all`
3. Start the UI: `npm --prefix traficom-integration\ui run dev`, open http://127.0.0.1:5173 and choose a
   persona (development sign-in, no passwords).
4. Pages: Dashboard, AI agent, Cases (Overview, Methods, Criteria, Evidence, Draft and review, Ask),
   IFIC issues, Finland relevance, Alerts, Source library, Upload, Users and access.
5. Judge demonstration without sign-in: `/demo` (or `?demo=judge`), synthetic data:
   [`docs/operations/JUDGE_DEMO.md`](docs/operations/JUDGE_DEMO.md).
6. Optional local AI: [`docs/operations/N8N_LOCAL_AI.md`](docs/operations/N8N_LOCAL_AI.md).

The Windows desktop package (Tauri) is built in CI and is unsigned.

### Android

The Android app (Capacitor) is built in CI and shares the web UI. It connects to an AstraSync backend
and identity provider reachable from the device. Push notifications are not configured. Device steps:
[`traficom-integration/ui/DEVICE_TESTING.md`](traficom-integration/ui/DEVICE_TESTING.md).

## Documentation

| Topic | Document |
| --- | --- |
| Architecture decisions | [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) |
| IFIC pipeline | [`docs/architecture/IFIC_PIPELINE.md`](docs/architecture/IFIC_PIPELINE.md) |
| Record store (Parquet/DuckDB) | [`docs/architecture/STAGE6_RECORD_STORE.md`](docs/architecture/STAGE6_RECORD_STORE.md) |
| API contract decisions | [`traficom-integration/contract/DECISIONS.md`](traficom-integration/contract/DECISIONS.md) |
| Backend configuration | [`traficom-integration/backend/README.md`](traficom-integration/backend/README.md) |
| Organizer clarifications | [`docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md`](docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md) |
| Requirements and status | [`docs/REQUIREMENTS_MATRIX.md`](docs/REQUIREMENTS_MATRIX.md), [`docs/DEVELOPMENT_PROGRESS.md`](docs/DEVELOPMENT_PROGRESS.md) |
| Operations runbook | [`docs/operations/RUNBOOK.md`](docs/operations/RUNBOOK.md) |
| Handoff / new PC | [`docs/NEW_PC_HANDOFF.md`](docs/NEW_PC_HANDOFF.md) |

## Technology stack

Python 3.11, FastAPI, SQLAlchemy/Alembic, PostgreSQL (SQLite in development), Parquet + DuckDB; React 18,
TypeScript, Vite, Tailwind; Tauri 2 (Windows), Capacitor 7 (Android); Ollama + n8n for local AI.

## Known limitations

No terrain data for P.1546; space PFD is a worst-case upper bound (not EPFD); some Table 21-4 entries are
not applied where applicability cannot be established; no production identity provider is configured.

## Licence

See [`LICENSE.md`](LICENSE.md). Third-party data keeps its own terms (ITU, Traficom open data CC BY 4.0,
Natural Earth public domain).
