# AstraSync development progress

Last updated: 2026-11-08. On a new PC start with [`NEW_PC_HANDOFF.md`](NEW_PC_HANDOFF.md). Read this first in a new session, then check `git log` and open PRs.
Update it in the PR that changes the state. Requirement-level status:
[`REQUIREMENTS_MATRIX.md`](REQUIREMENTS_MATRIX.md). Decisions:
[`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md).

**Requirements source.** The v3 documentation (PRD, TRD, IPD, BSD, quality charter, architecture)
is not in this repository. It is kept at
`Since_AI_Traficom/Since_AI_Traficom/AstraSync_documentation_v3/AstraSync/docs/` on the
development machine.

**Status words.** *Verified*: an automated test or recorded device run shows it. *Synthetic only*:
verified only on challenge or made-up data. *Blocked*: needs an external input, named below.

## Stage status

| Stage | Status | Evidence | What is missing |
| --- | --- | --- | --- |
| 0 Contract | Verified | Contract tests in CI; OpenAPI `1.0.0-draft.5` | BSD update for DECISIONS entries |
| 1 Secure skeleton | Verified on the local test IdP | Auth/authorization tests, deny by default | Real identity provider |
| 2 Source library | Verified on real data, including ITU IFIC | Workbook (874 rows) and live M4 (5,917 rows); ITU Space IFIC 3073/3074 and Terrestrial BR IFIC 3075/3076 discovered, downloaded, verified and parsed by the live pipeline; 3076 reconciles with the ITU ReadMe per part. Pipeline: [`architecture/IFIC_PIPELINE.md`](architecture/IFIC_PIPELINE.md) | Full BR IFIC DVD content (sold by ITU) not used |
| 3 Space RF | In progress, real data | Every 3074 notice screened (stages A–E, change vs 3073); free-space PFD upper bounds for downlink groups; GSO geometry over a 500-node Finland grid (minimum slant range, its location and elevation) and NGSO reach of Finland; published-data anomaly detection | Directional/NGSO PFD with patterns, EPFD, approved RR Article 21 criteria |
| 4 Terrestrial RF | Implemented and validated method; criterion applied on real data | ITU-R P.1546-6 port reproduces all 54 WP 3K reference cases (≤ 5.1e-5 dB); 3076 land-mobile notices evaluated along Finland's land borders (Natural Earth) and territorial-sea outer limit (Traficom WFS), 5 km sampling, against ECC T/R 25-08 A1.2.3 (edition 6 June 2025; >470 MHz as organizer-approved challenge extension): 6 coordination-threshold exceedances (5 with Finland in the coordination data), 42 below; workbook bandwidth mismatches normalized (smaller value) | Terrain data; 1 % time variant for digital systems; service-specific criteria for exposed Finnish stations |
| 5 Case UI and evidence | Verified; IFIC cases from real data; local AI verified live | HIGH findings open cases automatically (G27); `/ific` screen with ranked findings, stage reasons and the T/R 25-08 criterion panel; deterministic and grounded-LLM drafting (G28) through the local n8n/Ollama webhook, with one retry on a refused reply; grounded case questions (`POST /cases/{id}/questions`, Ask tab); judge demonstration `/demo` (`?demo=judge`) on a generated synthetic dataset, also the offline fallback from the sign-in page; XLSX evaluation workbooks | Lovable-generated screens; free-form chat across cases |
| 6 Large data | In progress, synthetic only | L1 4 GiB upload resilience; storage analysis (39.5× in PostgreSQL); Parquet/DuckDB record store with identical API answers; re-index command; dev stack on the record store. Report: [`architecture/STAGE6_RECORD_STORE.md`](architecture/STAGE6_RECORD_STORE.md) | 10M/50M rows, checkpoint resume inside a parse |
| 7 Native and alerts | Verified on CI package and emulator (PR #7) | Windows W1–W3, W5–W12; Android A1–A8 | Android push gateway, signed packages, real IdP |
| 8 Security and operations | Largely implemented | Secret scan, dependency audits, SBOMs (`supply-chain.yml`); parser process isolation (A16); `/operations/metrics`, `/healthz`, `/readyz` (G25); verified backup/restore; runbook `docs/operations/RUNBOOK.md`; PostgreSQL connection lifecycle fixed (engine disposed per app) | TLS, encryption at rest, OS-level parser sandbox, metrics export, threat model |
| 9 Extended methods | Not started | | P.1812/P.452, NGSO, EPFD |
| 10 Optional | Not started | | |

## Active work and next tasks

Frontend-to-backend coverage (production React app, real API client, no sample data):

| Workflow | Screen | Status |
| --- | --- | --- |
| IFIC issue analysis | `/ific` | Real data: Space 3073/3074 and Terrestrial 3075/3076 through the live dev-stack pipeline; ranked findings with stage reasons |
| A Source acquisition | `/uploads` → `/sources` | Browser-verified against the dev stack (PR #23) |
| B Finland relevance | `/finland` → record inspector | Browser-verified (PR #21); service/geometry/technical stages not assessed (IFIC fields) |
| C Case investigation | `/cases`, `/cases/:id` | Verified in UI tests and on devices (Stage 5/7); methods are demo plugins plus `SPACE_PFD_FREE_SPACE` |
| D Expert review | Case inspector draft and review | Verified in UI tests (Stage 5); drafts come from the demo template agent, not an AI |
| E Alerts | `/alerts` | Verified in UI tests and on devices (Stage 7) |
| Operations | Overview → Processing | Browser-verified (PR #21) |
| Administration | `/admin/users` (Administrator only) | Browser-verified against the dev stack: list, roles, entitlement grant and revoke, own-account lock; every persona probed live |

Next tasks:

1. Criteria: enter and approve, with citations, the ECC T/R 25-08 trigger field strengths and the
   RR Article 21 PFD limits (A43); only then can margins be computed.
2. Space methods: directional PFD with notified patterns, NGSO time series, EPFD (S.1503).
3. Terrain data for P.1546 (heff, clearance angles) instead of heff = ha.
4. Configure and evaluate an approved LLM provider for `GroundedLlmDraftAgent`.
5. Administration follow-ups needing a policy decision: tenant moves and per-case grants.
6. Port the Lovable case-detail method table and provenance timeline into `CaseInspectorPage`.

## Launching the application (local demonstration)

From the repository root, with the backend virtualenv and UI dependencies installed:

1. Backend stack (local test identity provider on 8801, API on 8800, worker; synthetic demo
   data, the Parquet record store on by default): `traficom-integration/backend/.venv/Scripts/python
   traficom-integration/backend/tests/support/dev_stack.py all`
2. UI: `npm --prefix traficom-integration/ui run dev`, then open `http://127.0.0.1:5173` and
   choose a test persona (no passwords; local only).

**Other ports.** Where Windows reserves 8800/8801 (socket error 10048; see `netsh interface
ipv4 show excludedportrange protocol=tcp`), copy
`traficom-integration/backend/dev_stack.local.env.example` to `dev_stack.local.env` and set
`ASTRASYNC_DEV_API_PORT`/`ASTRASYNC_DEV_IDP_PORT` (environment variables override the file), then
put the matching `VITE_API_BASE_URL` and `VITE_OIDC_AUTHORITY` in
`traficom-integration/ui/.env.development.local`. Both files are git-ignored. The stack checks
the ports (1024–65535, all different, bindable on 127.0.0.1) before starting and says what to
change; issuer, discovery, JWKS, token `iss`, CORS and redirect URIs all derive from these values.

**Access denied after choosing a persona (fixed 2026-11-07).** Users are keyed by issuer plus
subject. The dev database had its personas under `http://127.0.0.1:8801`; after the IdP moved to
18801 its tokens carried a new issuer, no user matched, and the API answered 403
`USER_NOT_PROVISIONED`. The stack now moves only its own seeded personas to the current loopback
dev issuer at start (keeping their user IDs and grants) and provisions any missing ones. No
other identity is ever created or moved.

**Real sources (optional).** With `ASTRASYNC_DEV_REAL_SOURCES=1` in `dev_stack.local.env`, the
stack also registers the ITU Space and Terrestrial IFIC sources, Traficom M4 and a workbook
source, with the real parsers, P.1546 and PFD methods and the deterministic drafting agent.
Nothing downloads until an administrator checks a source (Source library, or
`POST /api/v1/admin/sources/{id}/check`); the dev issue range is 3073–3074 (space) and 3075–3076
(terrestrial). Upload the challenge workbook to `CHALLENGE-WORKBOOK`. Each indexed IFIC issue is
analysed automatically and appears under **IFIC issues**.

**Accounts.** There is no self-registration or automatic grant. Outside the dev stack the first
administrator is provisioned with `python -m astrasync_api.admin provision-user --tenant <t>
--issuer <iss> --subject <sub> --role ADMINISTRATOR`; after that, administrators use
**Users and access** (`/admin/users`, G26).
3. Real Traficom M4 data: configure the worker with the M4 source client and adapter (see
   "Enabling the real components"), register the source, and run the worker.

The dev stack is for local demonstration only: it is not packaged and refuses non-loopback use.

## Blockers

| Blocker | Affects | Needed |
| --- | --- | --- |
| Full BR IFIC (DVD/ISO, ITU sales) | Terrestrial data beyond the MDB extract; IFICs no longer online | Purchase decision; the public Space databases and terrestrial extracts are in use |
| No approved criterion edition | TR-REG-001/002, margins | User-approved, cited RR edition and table references |
| Lovable workspace | Priority D | The connected account shows workspace "My Lovable" with one unrelated 2025 project. Confirm it is Aosaf's sponsored workspace before creating a project |
| `LICENSE.md` background-IP statement | `astrasync-core-lib`, AT-H-09 | Team and legal decision |
| Android push gateway | TR-ALT-003, AT-P-06 | Firebase project or another approved gateway |
| Production IdP with MFA | TR-IDENT-001, AT-P-02 | An approved OIDC provider |

## Enabling the real components

Worker and API settings:

- `ASTRASYNC_RECORD_STORE_PATH=<dir>`: parsed records in the Parquet record store (Stage 6).
  Existing indexed artifacts: `python -m astrasync_api.records_cli build`, then `verify`.
- `ASTRASYNC_SOURCE_ADAPTERS=astrasync_data.traficom_workbook:TraficomWorkbookAdapter,astrasync_data.traficom_m4_table:TraficomM4TableAdapter`
- `ASTRASYNC_SOURCE_CLIENTS=traficom-m4=astrasync_api.connectors.traficom_opendata:TraficomFrequencyTableClient`,
  with the source registered as `endpoint_ref=traficom-m4`, type `M4_ALLOCATION`, rights "CC BY 4.0"
- `ASTRASYNC_RF_METHODS=astrasync_physics.space_pfd:SpacePfdFreeSpace`

## Delivery log

| PR | Merge | Content |
| --- | --- | --- |
| #7 | `e816af1` | Stage 7 device tests |
| #8 | `9297339` | Traficom workbook parser |
| #11 | `400f7a7` | `SPACE_PFD_FREE_SPACE` |
| #10 | `f1dfec4` | Traficom M4 open-data connector |
| #12 | `da7e9df` | Finland frequency relevance |
| #13 | `5df61ad` | Stage 6: L1, storage analysis, Parquet/DuckDB record store |
| #14 | `e361969` | Stage 6 completion, criteria registry, tracking docs |
| #15 | `9ccec11` | UI increment 1: Lovable tokens, Tailwind 4, app shell |
| #16 | `249065f` | Supply-chain checks, react-router patch, stricter return paths |
| #17 | merged | UI increment 2: status badges |
| #18 | merged | Parser isolation (A16) |
| #19 | merged | Operations metrics and probes; PostgreSQL connection-lifecycle fix (peak 99 → 4 connections) |
| #20 | merged | Verified backup/restore, operations runbook |
| #21 | merged | Finland relevance screen, overview processing panel, shell accessibility |
| #22 | merged | TR-NFR-006 case-list benchmark (50,000 cases, p95 ≤ 657 ms), records |
| #23 | `19b5660` | Source upload and processing status |
| #24 | `3f3136e` | Records and frontend coverage |
| #25 | `87c1cf8` | Dev sign-in fix, configurable dev ports, user administration (G26) |
| #26 | `934c864` | ITU IFIC acquisition and parsing, issue analysis (G27), P.1546-6, drafting agents (G28), `/ific` screen, evaluation outputs for 3074 and 3076 |

Seven commits up to `65997b2` carry a Claude co-author trailer; they are left unchanged (no
history rewrite). New commits carry no attribution.

## Machine set-up notes

- Git: `SCP619 <priyoshaktiman@gmail.com>` in the repo config, pushes through the
  `github-scp619` SSH alias. `gh` is at `C:\Program Files\GitHub CLI\gh.exe`.
- Android: JDK 21, SDK in `%LOCALAPPDATA%\Android\Sdk`, emulator `astrasync-e2e`.
- No Rust or Visual Studio Build Tools locally, so Windows packages come from CI.
- The real workbook lives outside the repo; point `ASTRASYNC_TRAFICOM_WORKBOOK` at it for golden
  tests. A local PostgreSQL 16 (pgserver) can run the suite with `ASTRASYNC_TEST_DATABASE_URL`.
- Windows: `npm run contract:drift` reports drift only from CRLF line endings; compare with
  `git diff --ignore-cr-at-eol`.
