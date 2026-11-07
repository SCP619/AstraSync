# AstraSync development progress

Last updated: 2026-11-07. Read this first in a new session, then check `git log` and open PRs.
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
| 2 Source library | Verified; real data for the workbook and M4 | AT-H-01: real workbook SHA-256 `bb7f481f…`, 874 rows. Live Traficom M4 table: 5,917 rows discovered, archived, parsed, indexed (`ASTRASYNC_LIVE_SOURCES=1`) | Authorised IFIC adapters (blocked) |
| 3 Space RF | In progress | `SPACE_PFD_FREE_SPACE`, Tier 1 vectors, runs through the analysis runner with no margin | Directional/NGSO PFD, EPFD, criterion resolver, notice mapping (need IFIC data) |
| 4 Terrestrial RF | Blocked | | Two real IFIC issues, validated P.1546 |
| 5 Case UI and evidence | Verified with demo plugins | Case workflow, reviewer API, inspector, 91 UI tests | Real relevance stages, methods and draft agent |
| 6 Large data | In progress, synthetic only | L1 4 GiB upload resilience; storage analysis (39.5× in PostgreSQL); Parquet/DuckDB record store with identical API answers; re-index command; dev stack on the record store. Report: [`architecture/STAGE6_RECORD_STORE.md`](architecture/STAGE6_RECORD_STORE.md) | 10M/50M rows, checkpoint resume inside a parse |
| 7 Native and alerts | Verified on CI package and emulator (PR #7) | Windows W1–W3, W5–W12; Android A1–A8 | Android push gateway, signed packages, real IdP |
| 8 Security and operations | Largely implemented | Secret scan, dependency audits, SBOMs (`supply-chain.yml`); parser process isolation (A16); `/operations/metrics`, `/healthz`, `/readyz` (G25); verified backup/restore; runbook `docs/operations/RUNBOOK.md`; PostgreSQL connection lifecycle fixed (engine disposed per app) | TLS, encryption at rest, OS-level parser sandbox, metrics export, threat model |
| 9 Extended methods | Not started | | P.1812/P.452, NGSO, EPFD |
| 10 Optional | Not started | | |

## Active work and next tasks

1. Merge open PRs: #20 (backup/restore), #21 (Finland screen, overview processing panel), and
   the case-list benchmark PR.
2. UI: an upload screen (workflow A has backend endpoints but no production screen yet), the
   case-detail method table and provenance timeline from the Lovable design, accessibility checks.
3. Scientific: no teammate modules in the repo (`traficom-integration/agent` is empty);
   `RegistryCriterionResolver` ships no criteria. Service, geometry and technical relevance
   gates need IFIC field definitions.

## Launching the application (local demonstration)

From the repository root, with the backend virtualenv and UI dependencies installed:

1. Backend stack (local test identity provider, API on 8800, worker; synthetic demo data, the
   Parquet record store on by default): `traficom-integration/backend/.venv/Scripts/python
   traficom-integration/backend/tests/support/dev_stack.py all`
2. UI: `npm --prefix traficom-integration/ui run dev`, then open `http://127.0.0.1:5173` and
   choose a test persona (no passwords; local only).
3. Real Traficom M4 data: configure the worker with the M4 source client and adapter (see
   "Enabling the real components"), register the source, and run the worker.

The dev stack is for local demonstration only: it is not packaged and refuses non-loopback use.

## Blockers

| Blocker | Affects | Needed |
| --- | --- | --- |
| No authorised ITU BR IFIC sample or access route | Stages 2 (IFIC), 3, 4, 9; AT-H-03/04, AC-11 | An authorised IFIC file and its terms |
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
