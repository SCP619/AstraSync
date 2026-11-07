# Contract decisions for joint review

TRD section 1.1 says conflicts must not be resolved silently. Each entry is a reversible default, applied in contract `1.0.0-draft.1`, that both contributors need to confirm and then reflect in the BSD. BSD field names win unless stated otherwise.

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
| G10 | Relevance labels and reason codes have no closed list beyond `FREQUENCY_MATCH` | Validated `UPPER_SNAKE_CASE` codes. The relevance owner should publish the list |

## Assumptions

| # | Assumption | To revisit |
| --- | --- | --- |
| A1 | Contract code lives in `traficom-integration/backend/`. `astrasync-core-lib` imports nothing from it; its methods only need to match the protocol shape | If the Data/AI contributor prefers a shared package |
| A2 | Administrators get no case or source-content capability by default. Security says "scope-controlled", so wider access needs another role | Stage 1 policy |
| A3 | Case export is reviewer-only by default | Stage 5 |
| A4 | `SourceAdapter` and `CriterionResolver` signatures go beyond what the BSD states and are proposals | Data/AI review |
| A5 | No identity provider is chosen. All API routes return `401` until OIDC is added | Stage 1 ADR |

## Outside the contract: needs a team decision

- **Docs are not in the repo.** `docs/architecture` and `docs/requirements` hold only `.gitkeep`, and the root `README.md` is a 5-line stub. The v3 package is kept outside this repository, so PRs cannot update the BSD alongside the contract.
- **`LICENSE.md` conflicts with the v3 docs.** It states that `astrasync-core-lib` is background IP under section 5.5, while README, IPD and the playbook say a folder name does not establish that. It also cites "5.3 / 5.4" without settling which applies. Confirm this before submission. It has not been changed.
