# AstraSync requirements matrix

Last updated: 2026-11-07. Sources: v3 `TRD.md` (TR-*, AT-*) and `PRD.md` (AC-*), kept outside the repo
at `Since_AI_Traficom/Since_AI_Traficom/AstraSync_documentation_v3/AstraSync/docs/requirements/`.

**Statuses** NOT_STARTED, IN_PROGRESS, IMPLEMENTED_UNVERIFIED, VERIFIED, BLOCKED, DEFERRED.
VERIFIED means the stated acceptance test passes **in automated tests or recorded runs**; the
Evidence column says on what data (synthetic, made-up fixture, real public data, device). No row is
production-ready on its own: see [Production-readiness blockers](#production-readiness-blockers).

Components: **BE** backend (`traficom-integration/backend`), **CORE** `astrasync-core-lib`,
**UI** web client (`traficom-integration/ui`), **NAT** Tauri/Capacitor clients, **OPS** CI/operations.

## Platform and identity

| ID | Component | Status | Evidence / tests | Limitations |
| --- | --- | --- | --- | --- |
| TR-PLAT-001 | NAT, UI | IMPLEMENTED_UNVERIFIED | Windows package from CI; W1–W3, W5–W12 automated on the CI package (PR #7) | Unsigned; real IdP not tested |
| TR-PLAT-002 | NAT, UI | IMPLEMENTED_UNVERIFIED | Debug APK from CI; A1–A8 automated on an Android 15 emulator (PR #7) | Unsigned debug build; no push; emulator only |
| TR-PLAT-003 | BE, UI | VERIFIED | Generated OpenAPI types; `contract.export --check`, `npm run contract:check` in CI | |
| TR-PLAT-004 | BE | VERIFIED | Analysis runs only server-side (`test_cases.py`, `test_space_pfd_analysis.py`) | |
| TR-PLAT-005 | NAT, BE | IMPLEMENTED_UNVERIFIED | Native PKCE sign-in, sign-out, revoke-sessions; device runs on the local test IdP | Real IdP and expiry/reconnect at scale not tested |
| TR-PLAT-006 | NAT, BE | IMPLEMENTED_UNVERIFIED | In-app inbox with catch-up; Windows local notifications | Android push blocked (no gateway) |
| TR-PLAT-007 | NAT | IMPLEMENTED_UNVERIFIED | Clients never download masters except by explicit signed download | No client storage inspection report |
| TR-IDENT-001 | BE | IMPLEMENTED_UNVERIFIED | OIDC issuer/audience/scope/MFA claims validated (`test_authentication.py`) | Real approved IdP not configured |
| TR-IDENT-002 | BE, UI | VERIFIED | Deny by default, tenant, classification, entitlement, case access (`test_authorization.py`, `test_permissions.py`, `test_source_library.py`); user, role and source-entitlement administration with tenant scope and no self-changes (G26, `test_admin_users.py`, `AdminUsersPage.test.tsx`; browser-checked against the dev stack) | Synthetic fixtures; no tenant moves or per-case grants (policy decision) |
| TR-IDENT-003 | BE | VERIFIED | Role matrix tests; Analyst cannot approve; Admin has no data bypass (also checked on the live dev stack: Administrator gets 403 on cases); non-administrators cannot escalate | |
| TR-IDENT-004 | NAT | IMPLEMENTED_UNVERIFIED | Tokens in OS secure storage on native builds | No packaged-app security scan |
| TR-IDENT-005 | BE, UI | IMPLEMENTED_UNVERIFIED | Session revocation and deactivation from the admin screen apply to tokens already issued (401/403 on the next request; `test_admin_users.py`, live dev stack); device revocation stops pushes (A26) | Device-bound tokens not implemented |
| TR-IDENT-006 | BE | VERIFIED | Audit events for denials, writes, exports, downloads (`test_source_library.py`); every administration change twice (authorised request, committed change) with actor, tenant and request ID (`test_admin_users.py`) | Anonymous failures logged only (A11) |

## Sources, integrity and library

| ID | Component | Status | Evidence / tests | Limitations |
| --- | --- | --- | --- | --- |
| TR-SRC-001 | BE | VERIFIED | Source registry with rights, mode, classification | Retention policy field not enforced |
| TR-SRC-002 | BE | VERIFIED | Polling with ETag versions, dedupe, MANUAL_REQUIRED (`test_traficom_opendata_*`) | Traficom M4 only; no IFIC feed |
| TR-SRC-003 | CORE, BE | BLOCKED | Adapter interface and two real adapters exist | No authorised ITU BR IFIC sample (API/A, CR/C, AP30) |
| TR-SRC-004 | CORE, BE | VERIFIED | M4 (`M4_ALLOCATION`) and special-interest workbook are distinct source types; live M4 run 5,917 rows; real workbook 874 rows | |
| TR-SRC-005 | BE | IMPLEMENTED_UNVERIFIED | Server-side clients only; outage never read as retraction | No credentialed source yet |
| TR-SRC-006 | BE | VERIFIED | Resumable multipart upload, 4 GiB L1 run (resume, SHA-256, crash recovery) | Upload path; source-side resumable download not exercised at 4 GB |
| TR-SRC-007 | BE | IMPLEMENTED_UNVERIFIED | Immutable masters, exact SHA-256, revisions | Encryption at rest not implemented (local demo store) |
| TR-SRC-008 | BE | VERIFIED | Separate timestamps on artifacts and connectors | |
| TR-SRC-009 | BE | VERIFIED | Revised bytes create a new revision; old bytes kept | |
| TR-SRC-010 | BE | IMPLEMENTED_UNVERIFIED | Failure states and source-health alerts | Storage exhaustion not injected |
| TR-SRC-011 | BE | IMPLEMENTED_UNVERIFIED | Raw masters and derived index/datasets separate | Retention/erasure workflow not built |
| TR-SRC-012 | BE | IMPLEMENTED_UNVERIFIED | `records_cli build` reproducible dataset rebuild with count check | Issue backfill from publishers not built |
| TR-INT-001 | BE | VERIFIED | Assembled SHA-256 and byte count recomputed; L1 4 GiB match | |
| TR-INT-002 | BE | VERIFIED | Uploader manifest match never reported as publisher verification | |
| TR-INT-003 | BE, CORE | IMPLEMENTED_UNVERIFIED | Magic-byte dispatch, XLSX via defusedxml/openpyxl, quarantine on parser refusal | No archive-bomb or spoofing corpus |
| TR-INT-004 | CORE, BE | VERIFIED | Sheet/row identities preserved; deterministic reparse; adapters isolated in a child process (A16, `test_parser_sandbox.py`) | Process isolation only |
| TR-INT-005 | CORE | VERIFIED | Raw values kept beside parsed units (`test_units.py`, workbook golden) | |
| TR-INT-006 | CORE | VERIFIED | Field-level findings block dependent calculations | |
| TR-INT-007 | CORE | VERIFIED | No repair or imputation (A33) | |
| TR-INT-008 | BE | VERIFIED | Quarantine on mismatch and parser refusal | |
| TR-INT-009 | BE | VERIFIED | Parsed/accepted/flagged/rejected reconciliation; Parquet manifest counts | |
| TR-INT-010 | BE | VERIFIED | Lineage artifact → record → case evidence | |
| TR-INT-011 | CORE | NOT_STARTED | Unknown formats are refused | No `.mdb`/`.accdb` adapter |
| TR-LIB-001 | BE, UI | IMPLEMENTED_UNVERIFIED | Rights-filtered search by text, station, frequency | No date/notice-type/satellite filters (needs IFIC fields) |
| TR-LIB-002 | BE, UI | VERIFIED | Indexed record, original preview, separately authorised download | |
| TR-LIB-003 | BE, UI | VERIFIED | Inspector shows artifact hash, trust level, location, raw and normalised fields | |
| TR-LIB-004 | BE | IN_PROGRESS | Parquet/DuckDB record store; 200k-row benchmark p95 ≤ 52 ms | 10M+ rows not measured |
| TR-LIB-005 | UI | IMPLEMENTED_UNVERIFIED | Freshness, warnings and eligibility shown | No accessibility audit |
| TR-LIB-006 | BE | VERIFIED | Entitlements in index execution, preview, download, and Parquet dataset filtering | |
| TR-LIB-007 | BE, UI | NOT_STARTED | | |

## Relevance, RF methods and criteria

| ID | Component | Status | Evidence / tests | Limitations |
| --- | --- | --- | --- | --- |
| TR-REL-001 | BE | VERIFIED | Distinct domains and source types | |
| TR-REL-002 | BE | BLOCKED | | Needs consecutive real IFIC issues |
| TR-REL-003 | BE | BLOCKED | | Same |
| TR-REL-004 | BE, UI | IN_PROGRESS | Frequency stage on real data (`test_relevance.py`); `/finland` screen shows the stages, unassessed ones as not assessed (PR #21, browser-checked) | Service, geometry, technical stages need IFIC fields |
| TR-REL-005 | BE, UI | VERIFIED | Overlap labelled a screening signal | |
| TR-REL-006 | BE | VERIFIED | `INSUFFICIENT_DATA` candidates kept with reasons | |
| TR-REL-007 | BE | NOT_STARTED | | Prioritisation rules need agreement |
| TR-RF-001 | BE | VERIFIED | Method registry from plugins with versions | |
| TR-RF-002 | BE | VERIFIED | Applicability separate from run status | |
| TR-RF-003 | BE | VERIFIED | All applicable methods run; analysis lane separate | |
| TR-RF-004 | CORE | IMPLEMENTED_UNVERIFIED | `SPACE_PFD_FREE_SPACE`, Tier 1 vectors (`test_space_pfd.py`) | Needs scientific review (A35) and a real notice |
| TR-RF-005 | CORE | NOT_STARTED | | Orbit/pattern data needed |
| TR-RF-006 | CORE | NOT_STARTED | | |
| TR-RF-007 | CORE | NOT_STARTED | | |
| TR-RF-008 | CORE | BLOCKED | | Validated P.1546 implementation and real terrestrial inputs |
| TR-RF-009 | CORE | NOT_STARTED | | |
| TR-RF-010 | BE | VERIFIED | Immutable method runs with input snapshot, versions, build SHA | |
| TR-RF-011 | BE, CORE | VERIFIED | Missing/invalid inputs refused with reasons | |
| TR-RF-012 | BE | VERIFIED | Comparison groups by metric and reference conditions | |
| TR-RF-013 | CORE | IN_PROGRESS | Tier 1 analytic vectors for PFD | Tiers 2–4 need reference cases and expert review |
| TR-REG-001 | BE | BLOCKED | Criteria registry with mandatory edition, citation and approval (`criteria.py`, A43) | No approved criteria: cited RR edition needs user approval; M4 edition unnamed by API (A36) |
| TR-REG-002 | BE | IMPLEMENTED_UNVERIFIED | `RegistryCriterionResolver`: metric, frequency and declared conditions; unknown values give UNVERIFIED (`test_criteria.py`, made-up limits) | Real criteria entries need scientific review |
| TR-REG-003 | BE | VERIFIED | Margin null unless verified criterion (`test_cases.py`) | |
| TR-REG-004 | BE | VERIFIED | `margin_db = predicted - limit` for upper bounds only | |
| TR-REG-005 | BE, UI | IMPLEMENTED_UNVERIFIED | Labels exist; some findings not produced until rules agreed (A18) | |
| TR-REG-006 | BE | VERIFIED | No send endpoint; drafts need reviewer approval | |

## Cases, AI, alerts, API

| ID | Component | Status | Evidence / tests | Limitations |
| --- | --- | --- | --- | --- |
| TR-CASE-001 | BE | VERIFIED | Case links notice, relevance, source, run, methods, criterion | Demo data |
| TR-CASE-002 | UI | VERIFIED | Split-pane inspector (UI tests) | |
| TR-CASE-003 | BE, UI | IMPLEMENTED_UNVERIFIED | `GET /cases/{id}/export` (`CASE_EXPORT`) returns the evidence pack: evidence links (artifact hash, record, relevance), analysis runs with method and criterion checks, drafts marked unapproved, review events; audited (`test_cases.py::test_export_contains_the_chain_and_marks_unapproved_drafts`, restricted-export test) | Links are not re-verified (hash re-check) at export time; JSON only, no signed bundle |
| TR-CASE-004 | BE | VERIFIED | Append-only review events, role-protected | |
| TR-CASE-005 | BE, UI | IMPLEMENTED_UNVERIFIED | Drafts from evidence, pending approval, demo agent | No real `EvidenceDraftAgent` |
| TR-AI-001 | BE | IMPLEMENTED_UNVERIFIED | Agent cannot write method results (API) | No real agent |
| TR-AI-002 | BE | IMPLEMENTED_UNVERIFIED | Citation check on drafts | No real agent |
| TR-AI-003 | BE | VERIFIED | Classification policy (`ASTRASYNC_AI_CLASSIFICATIONS`) | |
| TR-AI-004 | BE | NOT_STARTED | | Needs agent and adversarial corpus |
| TR-AI-005 | BE | VERIFIED | Workflows run with no agent configured | |
| TR-ALT-001 | BE | VERIFIED | Versioned rule-based events (`test_alerts.py`) | |
| TR-ALT-002 | BE | VERIFIED | Outbox and separate lane | |
| TR-ALT-003 | BE, NAT | BLOCKED | Inbox and Windows local notifications | Android push gateway |
| TR-ALT-004 | BE | VERIFIED | Dedupe, retry, ack, history | Escalation policy starting values (A27) |
| TR-ALT-005 | BE, NAT | VERIFIED | Minimal payloads; deep links re-checked | |
| TR-ALT-006 | BE, UI | VERIFIED | Source vs scientific alerts; severity wording | |
| TR-API-001 | BE | VERIFIED | OpenAPI with typed errors and policies | |
| TR-API-002 | BE | VERIFIED | Upload sessions; 4 GiB L1 | |
| TR-API-003 | BE | IMPLEMENTED_UNVERIFIED | Server-side paging and limits | Million-row API test not run end to end |
| TR-API-004 | BE | IMPLEMENTED_UNVERIFIED | CORS, path and query validation; DuckDB sandbox | No fuzz suite |
| TR-API-005 | BE | VERIFIED | Short-lived ACL-checked download links | |
| TR-API-006 | BE | VERIFIED | No endpoint posts validated results | |

## Non-functional, security, UX

| ID | Component | Status | Evidence / tests | Limitations |
| --- | --- | --- | --- | --- |
| TR-NFR-001 | BE | IN_PROGRESS | 4 GiB upload verified (L1) | 10 GB not run (directive); real formats/network not measured |
| TR-NFR-002 | BE | IN_PROGRESS | Parquet/DuckDB record store | Tens of millions of rows not measured |
| TR-NFR-003 | BE | IMPLEMENTED_UNVERIFIED | No hardcoded ceilings; queue-based | Load profiles not run |
| TR-NFR-004 | BE | IN_PROGRESS | DuckDB memory/thread limits; parser memory/time limits (A16); queue backlog in `GET /operations/metrics` (G25) | No per-tenant quotas |
| TR-NFR-005 | BE | VERIFIED | Idempotent retries, crash-safe publication (`test_record_store.py`, `test_source_library.py`) | No checkpoint resume inside a parse |
| TR-NFR-006 | BE | VERIFIED | 50,000 synthetic cases on local PostgreSQL 16: every list query p95 ≤ 657 ms (text search; others ≤ 282 ms), target 2 s (`benchmarks/case_list.py`, `results/case-list-50k.json`) | Developer laptop, not production-like hardware; function-level timing without HTTP |
| TR-NFR-007 | BE | IMPLEMENTED_UNVERIFIED | Upload init 0.02 s locally | Not on production-like hardware |
| TR-NFR-008 | BE | VERIFIED | Preview without master transfer (`test_preview_search_and_record_never_touch_the_master`) | |
| TR-NFR-009 | BE | IN_PROGRESS | Benchmarks record bytes/s, rows/s, RSS, expansion; runtime backlog, failures, outbox and storage counts (`test_operations.py`) | No time-series export (Prometheus/OTel) |
| TR-NFR-010 | BE, OPS | IMPLEMENTED_UNVERIFIED | `astrasync_api.backup` create/verify/restore with hash and count verification (`test_backup.py`); runbook | Encryption and lifecycle of backups, scheduled drills in a real deployment |
| TR-NFR-011 | BE | IMPLEMENTED_UNVERIFIED | Separate alert lane | Not stress-tested |
| TR-SEC-001 | OPS | NOT_STARTED | | TLS/encryption are deployment work |
| TR-SEC-002 | OPS | VERIFIED | Gitleaks over full history in CI (`supply-chain.yml`), clean | Packaged-build inspection not done |
| TR-SEC-003 | BE | VERIFIED | Five classifications enforced | |
| TR-SEC-004 | BE, CORE | IMPLEMENTED_UNVERIFIED | Separate parser process with memory/time limits, scrubbed environment, JSON-only channel (`test_parser_sandbox.py`); defusedxml | No OS sandbox, decompression quotas or adversarial corpus |
| TR-SEC-005 | OPS | IN_PROGRESS | pip-audit and npm audit in CI | No threat model or ASVS/MASVS checklist yet |
| TR-SEC-006 | OPS | IN_PROGRESS | Lockfiles; CycloneDX SBOMs in CI | Release signing (keys not provided) |
| TR-SEC-007 | — | BLOCKED | | Legal review |
| TR-SEC-008 | — | BLOCKED | | `LICENSE.md` background-IP question |
| TR-SEC-009 | BE | IMPLEMENTED_UNVERIFIED | Entitlements on indexes, datasets, previews, notifications | Backups/telemetry not built |
| TR-UX-001 | UI | IMPLEMENTED_UNVERIFIED | Library → inspector → case flow; Finland screen links matches to records; Lovable tokens, shell and status badges integrated (PRs #15, #17, #21) | Case-detail method table and provenance timeline from the Lovable design not yet ported |
| TR-UX-002 | UI | IMPLEMENTED_UNVERIFIED | Units and method versions shown | |
| TR-UX-003 | UI | IMPLEMENTED_UNVERIFIED | Text labels with colour | No audit |
| TR-UX-004 | UI, NAT | IN_PROGRESS | | Virtualised tables not built |
| TR-UX-005 | UI | VERIFIED | Synthetic and warning labels (UI tests) | |
| TR-UX-006 | UI | IN_PROGRESS | | No accessibility suite |
| TR-UX-007 | UI | VERIFIED | Upload screen reports hashing, part progress, server verification and the job state as returned (PR #23; browser-checked against the dev stack: PARTIAL with `PARSER_UNAVAILABLE` shown honestly) | Uploads above 256 MiB go to the command-line path |
| TR-UX-008 | UI, CORE | IMPLEMENTED_UNVERIFIED | Bilingual workbook headers kept as aliases | |

## Acceptance tests

| ID | Status | Evidence / blocker |
| --- | --- | --- |
| AT-H-01 | VERIFIED | Real workbook: SHA-256 `bb7f481f…`, 874 rows, 22 columns, anomalies flagged |
| AT-H-02 | VERIFIED | Station/frequency search and original-linked preview without the master (synthetic and real workbook) |
| AT-H-03 | BLOCKED | Needs a real space notice (IFIC) and a cited criterion |
| AT-H-04 | BLOCKED | Needs consecutive real terrestrial issues and validated P.1546 |
| AT-H-05 | VERIFIED | Missing inputs never produce numbers (`test_cases.py`, `test_space_pfd*.py`) |
| AT-H-06 | VERIFIED | Method ID, version, inputs, units, provenance on every run |
| AT-H-07 | VERIFIED | Demo uses made-up fixtures, labelled |
| AT-H-08 | VERIFIED | Simulated events labelled |
| AT-H-09 | BLOCKED | IP/licence manifest needs team decision |
| AT-P-01 | IN_PROGRESS | CI packages; device runs on emulator and CI Windows; unsigned |
| AT-P-02 | IN_PROGRESS | Tests on local IdP; real MFA IdP missing |
| AT-P-03 | IN_PROGRESS | 4 GiB upload path verified; 10 GB and real source not run |
| AT-P-04 | NOT_STARTED | 10M/50M rows |
| AT-P-05 | IN_PROGRESS | M4 polling verified |
| AT-P-06 | BLOCKED | Android push gateway |
| AT-P-07 | BLOCKED | Scientific review of methods |
| AT-P-08 | IN_PROGRESS | Restore drill verified on SQLite (`test_backup.py`): rows, master SHA-256, datasets; production drill pending |
| AT-P-09 | BLOCKED | Legal and licence sign-off |
| AT-P-10 | NOT_STARTED | Usability/accessibility study |
| AC-01–AC-06 | VERIFIED on synthetic/demo data | Trace, validation, method states, run provenance, metric separation, margin rules |
| AC-07 | BLOCKED | Real terrestrial issues |
| AC-08 | IN_PROGRESS | Frequency gate only |
| AC-09 | BLOCKED | Real draft agent |
| AC-10 | VERIFIED | Reviewer approval and audit (`test_cases.py`) |
| AC-11 | BLOCKED | Real/authorised space and terrestrial cases |
| AC-12 | IN_PROGRESS | Benchmarks and instructions in `docs/architecture/STAGE6_RECORD_STORE.md` |
| AC-13 | IN_PROGRESS | See AT-P-01 |
| AC-14 | VERIFIED | Authorization and deep-link tests |
| AC-15 | IN_PROGRESS | 4 GiB verified; 10 GB not run |
| AC-16 | NOT_STARTED | Load profiles |
| AC-17 | BLOCKED | Android push |
| AC-18 | BLOCKED | Reviews |
| AC-19 | IN_PROGRESS | Error states exist; usability not tested |

## Production-readiness blockers

1. No authorised ITU BR IFIC data, so no real space or terrestrial investigation (AT-H-03/04, AC-11).
2. No approved criterion source edition, real `CriterionResolver`, or scientific review of methods.
3. No production identity provider with MFA; local test IdP only.
4. No encryption at rest or TLS deployment; backup tool and runbook exist but no production restore drill.
5. Parsers are process-isolated with limits, but not OS-sandboxed or malware-scanned (A16).
6. Native packages unsigned; Android push gateway missing.
7. Legal, licence and IP decisions (`LICENSE.md`) pending.
