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
| 8 Security and operations | Not started | | Scans, backups, monitoring, sandboxed parsing (A16) |
| 9 Extended methods | Not started | | P.1812/P.452, NGSO, EPFD |
| 10 Optional | Not started | | |

## Active work

- **Stage 6 completion** (branch `scp619/stage6-completion`): `records_cli build|verify`,
  `ingest.build_record_dataset`, metadata cache, dev stack on the record store, 50-artifact
  benchmark, these tracking documents; plus the criteria-registry resolver (A43, Priority B).

## Next executable tasks

1. Merge the Stage 6 completion PR.
2. Priority B: no teammate scientific modules exist in the repo (`traficom-integration/agent` is
   empty). `RegistryCriterionResolver` is built and ships no criteria. The service, geometry and
   technical-readiness relevance gates need IFIC field definitions before rules can be written.
3. Priority C: Windows installer settings and deep links in CI; Android release build in CI
   (unsigned until keys are provided).
4. Priority D: Lovable design system, in the account owner's workspace (see blockers).
5. Priority E: secret scanning, dependency audit and SBOM in CI; parser isolation; backup/restore
   runbook.

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
