# AstraSync architecture decisions

Last updated: 2026-11-07. This is the index of decisions that shape the architecture. Every
contract-level decision, deviation and assumption, with its review owner, is recorded in full in
[`traficom-integration/contract/DECISIONS.md`](../traficom-integration/contract/DECISIONS.md)
(IDs A*, D*, G*); this file does not repeat them.

## System shape

| Area | Decision | Reference |
| --- | --- | --- |
| Services | FastAPI API and a separate worker process sharing one PostgreSQL database; durable jobs with leases (`FOR UPDATE SKIP LOCKED`), no separate broker yet | A12 |
| Contract | Pydantic models are the single source; OpenAPI and UI types are generated and checked in CI | Stage 0 |
| Plugins | `SourceAdapter`, `SourceClient`, `RFMethod`, `CriterionResolver`, `EvidenceDraftAgent` loaded from settings (`module:attribute`); the core library never imports the backend | A1 |
| Objects | Immutable masters through `ObjectStore`; a local implementation for DEMO only | A13 |
| Authorization | Server-side, deny by default: role, tenant, classification, source entitlement, case access; filters run inside queries | Stage 1, A7 |

## Data storage (Stage 6)

| Area | Decision | Reference |
| --- | --- | --- |
| Transactional | PostgreSQL: identities, tenants, permissions, jobs, sources, artifacts, integrity checks, audit, cases, reviews, drafts, alerts, dataset manifests | A38 |
| Parsed records | One immutable Parquet dataset per artifact (`records.parquet`, `findings.parquet`, zstd, 5,000-row row groups), read through DuckDB, on when `ASTRASYNC_RECORD_STORE_PATH` is set | A38 |
| Publication | Staging → fsync → SHA-256 → one directory rename → manifest committed with the indexed status; readers open manifest paths only | A39 |
| Query boundary | Fixed query templates with bound parameters; per-thread sandboxed DuckDB connection (store directory only, no extensions, locked settings, memory and thread limits) | A40 |
| Findings review | Overrides will be a PostgreSQL overlay; Parquet is never rewritten | A41 |
| Migration | `records_cli build` re-parses masters with the same parser version and publishes only on matching counts; PostgreSQL index rows are kept | A42 |

Measured basis: [`architecture/STAGE6_RECORD_STORE.md`](architecture/STAGE6_RECORD_STORE.md).

## Scientific integrity

| Area | Decision | Reference |
| --- | --- | --- |
| Margins | Only with a verified applicable criterion and matching conditions; otherwise null | A17, A18, TR-REG-003 |
| Findings | `INSUFFICIENT_DATA`, `POTENTIAL_LIMIT_EXCEEDANCE`, `EXPERT_REVIEW_REQUIRED` only until further rules are agreed | A18 |
| Units | Raw values kept; no repair, imputation or unit inference | A30–A33 |
| Space PFD | `SPACE_PFD_FREE_SPACE` takes EIRP and slant range as given; no bandwidth rescaling | A35 |
| Relevance | Closed intervals; overlap is a screening signal, never interference | A37 |
| Correspondence | Drafts only; reviewer approval; no send endpoint | TR-REG-006 |

## Clients

| Area | Decision | Reference |
| --- | --- | --- |
| Native | Tauri (Windows) and Capacitor (Android) wrap the same React client; PKCE with the system browser and custom scheme `fi.astrasync.app` | A24 |
| Notifications | Windows local notifications with inbox catch-up; Android push pending a gateway | A25, A26 |
| UI design | Lovable designs components in the account owner's workspace; code is reviewed and integrated locally, never pushed by Lovable | Directive 2026-11-07 |
