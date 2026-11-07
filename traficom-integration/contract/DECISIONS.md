# Contract decisions for joint review

TRD section 1.1 says conflicts must not be resolved silently. Each entry is a reversible default, applied in contract `1.0.0-draft.5`, that both contributors need to confirm and then reflect in the BSD. BSD field names win unless stated otherwise.

## Documentation conflicts

| # | Conflict | Default applied | Why |
| --- | --- | --- | --- |
| D1 | Finding status: PRD/dashboard list `POTENTIAL_LIMIT_EXCEEDANCE`, TRD-REG-005 lists `OVERLAP` and `PREDICTED_CRITERION_EXCEEDANCE` | PRD/dashboard list. An overlap is `relevance_label=FREQUENCY_MATCH`, not a finding | Keeps overlap out of the finding vocabulary |
| D2 | Method state: PRD has one list (`RUN`, `FAILED`, ...), BSD has `applicability` plus `execution_status` | BSD's two fields | BSD owns the method-run schema |
| D3 | `SPACE_PFD_SCENARIO` (PRD) vs `SPACE_PFD_TIME_SERIES` (RF methods) | `method_id` is a validated code, not an enum. **The registry owner picks one name** | Method IDs belong to the RF registry |
| D4 | Classification: BSD has 3 values, Security has 5 | Security's 5 | Safer superset; includes `CONFIDENTIAL_PARTNER` |
| D5 | Artifact states differ between Integrity, Source Acquisition and TRD | One merged `ArtifactStatus`. Origin trust stays in `publisher_auth_status` | Docs require these not to be conflated |
| D6 | Alert fields: `title`, `recipient_id` (Alert Engine) vs `safe_title`, `recipient_user_id` (BSD) | BSD names | BSD owns entity names |
| D7 | Push content: "opaque ID + safe title" (context strategy) vs "ID + generic category + timestamp" (Alert Engine) | ID, category, timestamp only | Stricter option; safe for lock screens |
| D8 | Source type: `FINLAND_FREQUENCY_INTEREST` (AFD) vs `CHALLENGE_SYNTHETIC_REFERENCE` (workbook profile) | Both kept: the workbook uses the second; a future real feed uses the first | Keeps synthetic data separately labelled |
| D9 | Query parameter `filename` (BSD) vs `file_name` (Source Acquisition); path `{source_record_id}` vs `{record_id}` | BSD spelling | BSD owns routes |
| D10 | Case detail may embed method runs or load them separately | Load from `GET /analyses/{id}`; the case holds `latest_analysis_run_id` | Inspector spec requires one canonical source |

## Gaps filled

| # | Gap | Default applied |
| --- | --- | --- |
| G1 | No way to get new signed part URLs, which a resumable 10 GB upload needs because URLs are short-lived | Added `POST /uploads/{id}/parts` |
| G2 | "View indexed record" and TR-LIB-003 have no route; only `/source-location` exists | Added `GET /source-records/{id}` with raw values, normalized values and findings |
| G3 | `/source-publications` has no table in BSD section 9, while Source Acquisition names `source_publications` | API model `SourcePublication`, mapped from `source_observations`. Table decision belongs to the Stage 2 migration |
| G4 | **`cases`, `notices`, `source_issues` and `analysis_runs` have no `tenant_id`**, though every query must be tenant-scoped | Tenant stays out of responses and comes from identity. **The Stage 2 schema must add tenant ownership** |
| G5 | `is_synthetic` is in the case API but not the `cases` table; `reference_station_records` fixes it to `true` | A boolean in the API. Real data will need `false`. Add it to the tables |
| G6 | Analysis states have no in-progress value | Added `QUEUED`, `RUNNING`, and `INPUT_SUPERSEDED` from RF methods section 10 |
| G7 | `comparison_status` has no vocabulary | `COMPARED`, `NOT_COMPARABLE`, `CRITERION_UNVERIFIED`, `REVIEW_REQUIRED` |
| G8 | Lower-bound thresholds have no documented margin convention | Any margin on them is rejected until a comparator is documented |
| G9 | DBD table columns `Satellite or station` and `Evidence quality` have no API field | **Not added.** Needs a definition, especially for evidence quality, before Stage 5 |
| G11 | `upload_sessions` had no source. Every artifact needs a registered source and its rights basis | Added `source_id` to `UploadCreateRequest` |
| G12 | `source_type` was missing from the client's view of a connector | Added to `SourceConnector` |
| G13 | `SourceLocationDetail` had two different `schema_version` fields (found by a Stage 2 test) | The record's is now `record_schema_version` |
| G14 | No route for streaming a part or original when object storage is local | Added `PUT /uploads/{id}/parts/{n}` and `GET /source-artifacts/{id}/content`. A managed store's signed URLs replace them |
| G15 | Workers have no contract for what a parser returns | Added `AdapterRecord`, published in OpenAPI |
| G16 | `acquisition_jobs` in BSD section 9 duplicates `job_runs` | One `job_runs` table with a new `ACQUIRE` type |
| G17 | `part_manifest_json` would need rewriting on each part | A separate `upload_parts` table |
| G18 | Alerts need a durable outbox from Stage 7, but events start now | `outbox_events` is written now and unconsumed until then |
| G19 | No route to read or edit drafts or read review history, though the inspector requires them | Added `GET /cases/{id}/drafts`, `PUT /cases/{id}/drafts/{draft_id}` and `GET /cases/{id}/reviews` |
| G20 | Nothing defined how a relevance result becomes a case | Added `CaseCandidate` and `cases.upsert_candidate`, for the relevance owner to call |
| G21 | BSD has no rule for a case's lead metric, or for its finding from a set of method runs | See A17 and A18 |
| G22 | `PUT /alerts/preferences` had no way to read current values | Added `GET /alerts/preferences` |
| G23 | ALERT_ENGINE has a reviewer escalation trigger, but nothing can raise it | Added `ReviewAction.ESCALATE` and `DomainEventKind.CASE_ESCALATED` |
| G10 | Relevance labels and reason codes have no closed list beyond `FREQUENCY_MATCH` | Validated `UPPER_SNAKE_CASE` codes. The relevance owner should publish the list |

## Assumptions

| # | Assumption | To revisit |
| --- | --- | --- |
| A1 | Contract code lives in `traficom-integration/backend/`. `astrasync-core-lib` imports nothing from it; its methods only need to match the protocol shape | If the Data/AI contributor prefers a shared package |
| A2 | Administrators get no case or source-content capability by default. Security says "scope-controlled", so wider access needs another role | Stage 1 policy |
| A3 | Case export is reviewer-only by default | Stage 5 |
| A4 | `SourceAdapter` and `CriterionResolver` signatures go beyond what the BSD states and are proposals | Data/AI review |
| A5 | No identity provider is chosen. The API validates any standards-compliant OIDC provider from settings. The choice stays open | Before staging |
| A6 | `users.sessions_revoked_before_utc` is added to the BSD `users` entity, to make session revocation enforceable | BSD update |
| A7 | `resource_entitlements` also has `tenant_id`, so an entitlement cannot apply across tenants | BSD update |
| A8 | Any provisioned user with no role can call `GET /me` and nothing else, so the client can explain the state | Stage 1 review |
| A9 | Client tokens stay in memory in the web preview, so a reload requires sign-in. Native storage comes in Stage 7 | Stage 7 |
| A10 | Reviewer reruns ("if granted" in Security) stay denied: no extra-capability grant exists yet | Stage 5 |
| A12 | The queue runs on the transactional database (`FOR UPDATE SKIP LOCKED`), so no separate broker is needed yet | Stage 6 benchmarks |
| A13 | Object-store access goes through `ObjectStore`. Only a local demo implementation exists, and it is refused outside `DEMO` | Before staging |
| A14 | The search index and raw record values are in PostgreSQL. Analytical Parquet and DuckDB stay with Data/AI. Tens of millions of rows are unproven | Stage 6 benchmarks |
| A15 | Connector status is tenant metadata, visible with `SOURCE_HEALTH_READ` without an entitlement. It has no file names or credentials | Stage 2 review |
| A16 | Adapters run inside the worker process. Sandboxing and malware scanning are not done yet | Stage 8; do not parse untrusted files in production before then |
| A17 | **Lead metric:** highest role (regulatory, engineering, verification, screening), then method ID. It is never chosen by value. If any verified margin is positive, the case shows that run so its summary can't hide it | **Scientific review** |
| A18 | **Findings:** no run succeeded gives `INSUFFICIENT_DATA`; any positive verified margin gives `POTENTIAL_LIMIT_EXCEEDANCE`; otherwise `EXPERT_REVIEW_REQUIRED`. `NO_IDENTIFIED_CONCERN`, `POTENTIAL_CONCERN` and `METHOD_DISAGREEMENT` are not produced until their rules are agreed | **Scientific review** |
| A19 | The method catalogue comes from RF_METHODS sections 2 and 3, including its metric and role labels. `SPACE_PFD_TIME_SERIES` is used for D3 until the registry owner decides | **Data/AI review** |
| A20 | Case access reuses source entitlements. Per-case assignment ("assigned/authorised" in Security) isn't modelled yet | Stage 8 |
| A21 | Case export needs `CASE_EXPORT` plus an `EXPORT` right on restricted data, and a reviewer can approve a draft with no second approver | Deployment policy |
| A22 | AI drafting is synchronous in the request. A slow provider holds one API thread | When a real agent exists |
| A23 | Native clients keep tokens in memory only, so there is no refresh token and no use yet for the OS credential vault that Security describes. Restarting signs in again | Usability testing on devices |
| A24 | Native sign-in uses the custom scheme `fi.astrasync.app` with PKCE. Android App Links would be stronger but need a production domain | Before release |
| A25 | Windows notifications are local while the app runs, with no server push. An inbox catches up on start | Windows delivery testing |
| A26 | Device revocation stops pushes. It doesn't end the session: that needs device-bound tokens, which A23 avoids. `revoke-sessions` ends sessions | Security review |
| A27 | Severity defaults and role routing in `alerts.DEFAULT_RULES` are starting values | **Team review** |
| A28 | Alert titles and previews are English only. Finnish needs a client-side catalogue | Usability testing |
| A11 | Audit covers denials by signed-in users, permitted writes, exports and downloads. Anonymous and invalid-token failures are logged only, so they cannot fill the audit table | Stage 8 |

## Outside the contract: needs a team decision

- **Docs are not in the repo.** `docs/architecture` and `docs/requirements` hold only `.gitkeep`, and the root `README.md` is a 5-line stub. The v3 package is kept outside this repository, so PRs cannot update the BSD alongside the contract.
- **`LICENSE.md` conflicts with the v3 docs.** It states that `astrasync-core-lib` is background IP under section 5.5, while README, IPD and the playbook say a folder name does not establish that. It also cites "5.3 / 5.4" without settling which applies. Confirm this before submission. It has not been changed.
