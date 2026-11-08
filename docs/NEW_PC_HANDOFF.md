# AstraSync: handoff for continuing on another PC

Written 2026-11-08 at `main` = `934c864` (merge of PR #26). Read this first, then
[`WINDOWS_DEVELOPMENT_SETUP.md`](WINDOWS_DEVELOPMENT_SETUP.md). A ready-to-paste prompt for a new
Claude Code session is in [`CLAUDE_RESUME_PROMPT.md`](CLAUDE_RESUME_PROMPT.md).

Everything below was checked against the repository and GitHub when written. Re-check the Git
state and CI yourself; this file does not update itself.

## 1. Project overview

AstraSync is the Since AI 2026 Traficom challenge solution ("Saving Earth from Space Interferers
Using Radio Frequencies"). It acquires ITU BR IFIC publications, finds notices relevant to Finland,
runs reproducible RF calculations, opens reviewable cases with evidence, and drafts correspondence
for an expert to approve. It never states interference or a limit exceedance without an approved
criterion.

| Part | Where | Technology |
| --- | --- | --- |
| API and worker | `traficom-integration/backend` (`astrasync_api`) | Python 3.11, FastAPI, SQLAlchemy, Alembic; OIDC bearer tokens; durable jobs with leases |
| Parsers and RF methods | `astrasync-core-lib` (`astrasync_data`, `astrasync_physics`) | Pure Python, loaded by name as plugins |
| Contract | `traficom-integration/contract` | Pydantic models → `openapi.json` → generated TypeScript |
| Clients | `traficom-integration/ui` | One React 18 + TypeScript UI (Vite); Windows via Tauri 2, Android via Capacitor 7 |
| Storage | | PostgreSQL (SQLite in tests and the dev stack) for metadata, access, jobs, audit; immutable object store for original files; Parquet + DuckDB record store for parsed records ([`architecture/STAGE6_RECORD_STORE.md`](architecture/STAGE6_RECORD_STORE.md)) |

Pipeline: discover → download (allow-listed HTTPS) → verify SHA-256 → quarantine or accept →
parse in an isolated process → records → for IFIC issues, a RELEVANCE job: change detection,
Finland relevance stages A–E, P.1546 / PFD calculations → stored findings → cases for HIGH items →
analysis runs → evidence-bound drafts → expert review → evidence export. Details:
[`architecture/IFIC_PIPELINE.md`](architecture/IFIC_PIPELINE.md).

Workflows in the UI: Source library and Upload (`/sources`, `/uploads`), IFIC issues (`/ific`),
Finland relevance (`/finland`), Cases (`/cases`), Alerts (`/alerts`), Users and access
(`/admin/users`).

## 2. Current development state

| Item | State |
| --- | --- |
| `main` | `934c864` — Merge PR #26 (IFIC pipeline) |
| Merged PRs | #7–#26. Latest: #25 dev sign-in, ports, user administration (merged 2026-11-07); #26 IFIC acquisition, parsing, relevance, P.1546, drafting, evaluation outputs (merged 2026-11-08) |
| Open PRs | The PR carrying this handoff (`scp619/new-pc-handoff`), documentation only |
| CI on PR #26 head `36f0dca` | All 8 checks passed: contract (backend lint, mypy, contract export check, pytest on SQLite **and PostgreSQL**, UI contract check, tests, build), core, Windows and Android compile checks, packaged Windows and Android test builds, dependency audit, secret scan |
| CI on `main` `934c864` | Running when this was written; check `gh run list --branch main` |
| Backend tests (local, SQLite) | 437 passed, 8 skipped |
| Core tests (local) | 169 passed with real-data variables set; 105 passed, 13 skipped without them (as in CI) |
| UI | 109 tests pass; typecheck, contract check and build pass |
| Native | CI compiles both packages on every PR. Device runs (Windows W1–W12, Android A1–A8 on emulator) were recorded on 2026-11-07, see `traficom-integration/ui/DEVICE_TESTING.md` |
| Unmerged or uncommitted work | None. Local branches `scp619/dev-auth-admin` and `scp619/ific-pipeline` are merged |

## 3. Implemented functionality

"Verified" means automated tests or a recorded run, on the data named.

| Area | Status |
| --- | --- |
| Authentication | OIDC (issuer, audience, scope, MFA claims), deny by default; dev identity provider with personas (`tests/support/dev_stack.py`). Verified |
| Authorization | Roles → capabilities, tenant isolation, classification and source entitlements in every list, search, analysis and export. Verified |
| Dev user provisioning | Personas keyed by issuer + subject; follow the configured dev issuer. Verified |
| Administration | `/admin/users`: users, roles, status, session revocation, source entitlements; audited; no self-changes. Verified, browser-checked |
| Source library and upload | Registry, resumable upload, SHA-256, immutable revisions, quarantine, isolated parsers, record store. Verified (4 GiB upload run) |
| ITU IFIC acquisition | Space and Terrestrial index discovery and download (`connectors/itu_brific.py`). Verified on real issues 3073–3076 through the live dev stack |
| ITU IFIC parsing | Space SNS v10 and Terrestrial MDB adapters (`itu_ific.py`). Verified on real data; 3076 reconciles with the ITU ReadMe |
| Finland relevance | Stages A–E, change detection (`ific_analysis.py`). Implemented on real data; rules not approved by Traficom |
| P.1546 | ITU-R P.1546-6 port; 54/54 WP 3K reference cases within 5.1e-5 dB. No terrain data (heff = ha) |
| Space PFD | Free-space upper bound only. Not EPFD, no antenna patterns |
| Case generation and RF analysis | Cases for HIGH IFIC findings; analysis runs with all applicable methods. Verified (live case: P.1546 31.75 dB(µV/m)) |
| Evidence drafting | Deterministic agent works; grounded LLM agent built and tested with a stub model only (no provider configured) |
| Expert review, evidence export | Append-only reviews, export pack. Verified on demo and IFIC cases |
| Alerts | Rules, SSE stream, devices; Android push gateway not configured (blocked) |
| Operations | `/healthz`, `/readyz`, `/operations/metrics`, backup/restore with verification, runbook |
| Windows desktop | Tauri package builds in CI; device run recorded; unsigned |
| Android | Capacitor APK builds in CI; emulator run recorded; push not configured |

## 4. Remaining requirements

From [`REQUIREMENTS_MATRIX.md`](REQUIREMENTS_MATRIX.md) (counts at writing: 64 verified rows, 32
implemented but unverified, 10 in progress, 6 not started, 4 blocked).

- **Blocked:** TR-REG-001 approved regulatory criteria (needs a cited, user-approved edition: ECC
  T/R 25-08 trigger values, RR Article 21 PFD limits; none may be invented); TR-ALT-003 Android push
  gateway; TR-SEC-007 legal review; TR-SEC-008 `LICENSE.md` background-IP question.
- **Not started:** TR-RF-005/006/007/009 (directional PFD with patterns, EPFD/NGSO time series,
  further propagation models), TR-LIB-007, TR-SEC-001 (TLS and encryption at rest).
- **In progress:** 10M+ row scale (TR-LIB-004, NFR-001/002), per-tenant quotas (NFR-004), metrics
  export (NFR-009), threat model (SEC-005), release signing (SEC-006), virtualised tables and
  accessibility suite (UX-004/006), RF validation tiers 2–4 (RF-013).
- **Scientific limits now:** no terrain data for P.1546; screening parameters (10 % time, 50 %
  locations, 10 m, rural) are AstraSync defaults; space PFD is an upper bound; priority weights are
  not expert-approved; special-interest stations are synthetic.
- **External:** live LLM provider and key; Firebase or another push gateway; production OIDC
  provider; code-signing certificate; optional ITU BR IFIC DVD for full terrestrial data.

## 5. Important directories and files

| What | Path |
| --- | --- |
| OpenAPI contract | `traficom-integration/contract/openapi.json` (generated by `python -m astrasync_api.contract.export`) |
| Contract models, enums, permissions | `traficom-integration/backend/astrasync_api/contract/` |
| Contract decisions (G*, A*) | `traficom-integration/contract/DECISIONS.md` |
| Generated TypeScript types | `traficom-integration/ui/src/api/schema.gen.ts` (`npm run contract:generate`) |
| API routes | `traficom-integration/backend/astrasync_api/routes.py` |
| Auth and permissions | `oidc.py`, `security.py`, `authz.py`, `identity.py`, `admin_api.py` in `astrasync_api/` |
| Migrations | `traficom-integration/backend/astrasync_api/migrations/versions/` (0001–0006) |
| Acquisition and connectors | `astrasync_api/acquisition.py`, `astrasync_api/connectors/` |
| Ingestion, sandbox, record store | `ingest.py`, `parser_sandbox.py`, `record_store.py` |
| IFIC parsers | `astrasync-core-lib/data/astrasync_data/itu_ific.py` |
| Relevance engine | `astrasync-core-lib/data/astrasync_data/ific_analysis.py`, `geo.py`; backend job `astrasync_api/ific_pipeline.py`, API `ific_api.py`; range screen `relevance.py` |
| RF methods | `astrasync-core-lib/physics/astrasync_physics/` (`p1546.py`, `terrestrial_p1546.py`, `space_pfd.py`); runner `astrasync_api/analysis.py`; criteria `criteria.py` |
| Drafting agents | `astrasync_api/drafting.py`; draft workflow in `cases.py` |
| Evaluation command | `astrasync-core-lib/data/astrasync_data/ific_evaluate.py` |
| Frontend | `traficom-integration/ui/src/` (pages by area: `admin/`, `alerts/`, `cases/`, `relevance/`, `sources/`; shell in `components/`) |
| Platform adapters | `traficom-integration/ui/src/platform/`, `src/auth/`; native projects `src-tauri/`, `android/` |
| Dev stack | `traficom-integration/backend/tests/support/dev_stack.py`, `dev_ports.py` |
| Tests | `traficom-integration/backend/tests/`, `astrasync-core-lib/tests/`, `traficom-integration/ui/src/**/*.test.tsx` |
| Evaluation reports | `evaluation/space_3074/`, `evaluation/terrestrial_3076/` |
| Requirements, progress, decisions | `docs/REQUIREMENTS_MATRIX.md`, `docs/DEVELOPMENT_PROGRESS.md`, `docs/ARCHITECTURE_DECISIONS.md` |
| Operations | `docs/operations/RUNBOOK.md` |

## 6. Engineering decisions to preserve

See [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) and the contract `DECISIONS.md`.

- Deny by default; every list, search, finding and export filtered by tenant, classification and
  source entitlement on the server. IFIC findings need READ on the issue and on every reference
  source used (G27).
- PostgreSQL holds metadata, access, jobs and the append-only audit trail; parsed records live in
  Parquet datasets read through DuckDB; originals are immutable.
- No fabricated data: synthetic fixtures are marked synthetic; nothing missing is defaulted.
- Scientific provenance on every result: method ID, version, implementation hash, inputs,
  assumptions, validation status.
- Frequency overlap is a screening signal, never interference. No regulatory finding without an
  approved criterion (A43). Space PFD is an upper bound, not EPFD.
- AI receives only stored evidence; its output is checked for citations, numbers and claims;
  correspondence is never sent automatically.
- One shared React UI for web, Tauri and Capacitor; the server stays authoritative.
- Git: commits and pushes as SCP619 only, `scp619/*` branches, PRs to `main`, no Claude attribution.

## 7. Known problems

Current:

- Two moderate `react-router` advisories (`npm audit`); the fix is a breaking major upgrade. Below
  the CI threshold.
- `.claude/launch.json` (tracked) names ports 8800/8801/5173; on a machine using port overrides the
  Claude browser preview for the dev stack does not match. Start the stack from a terminal instead.
- A full page reload signs the web UI out (tokens are memory-only by design).
- Space `act_code` meanings are unknown (SNS v9.1 dictionary NOTE 3 not available); the code is kept
  raw and not used for change type.

Resolved (history, do not re-fix): dev sign-in 403 after an issuer port change (PR #25); parser
sandbox crash when the child exited before its last lines were read (PR #26); distant stations
ranked HIGH on frequency alone (PR #26).

## 8. How to resume

1. Set up the PC ([`WINDOWS_DEVELOPMENT_SETUP.md`](WINDOWS_DEVELOPMENT_SETUP.md)) and run the smoke
   checks there.
2. Check CI on `main` and any open PRs.
3. Restore or re-download local data (setup guide, section 9) only if you need real-data tests or
   evaluation runs.
4. Then pick from section 4, in challenge-impact order: approved criteria entry (with the user),
   directional PFD / EPFD, terrain data for P.1546, LLM provider configuration, remaining
   production items.
