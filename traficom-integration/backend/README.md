# AstraSync backend

FastAPI service. **Status:** IPD stage 7, part way. Identity, authorization, audit, the source library, the case and review workflow, and alerts are implemented. No real push gateway exists, and native packages are unbuilt (see `ui/README.md`). No real RF method, criterion or AI agent is plugged in yet. Each operation's `x-implementation-status` in `contract/openapi.json` says what is real; other routes return `501` after authorization. MFA and the production identity provider have not been tested against a real provider. Object storage is local and demo-only; real ITU and workbook parsers and connectors do not exist yet.

## How access works

Each request passes these checks in order, before its body is read:

1. **Token (`oidc.py`):** signature against the provider's published keys, issuer, audience, expiry, required scopes and MFA evidence (`amr` or `acr`). Only asymmetric algorithms are possible.
2. **Identity (`identity.py`):** the issuer and subject must match a provisioned, active user. Roles and tenant always come from the database; those claims in a token are ignored.
3. **Capability (`security.py`):** the role must grant the capability the route declares in the contract. A v1 route cannot be registered without one.
4. **Object (`authz.py`):** **each route that touches a stored object must call `ObjectAccessPolicy`.** It checks tenant, data environment, classification and source entitlement, and answers a denial with the same `404` as a missing object. List and search routes apply the same rules inside the query.

Denied actions, permitted writes, and exports and downloads are recorded in `audit_events`. A write, export or download that cannot be audited does not proceed. Rejected tokens are logged with a reason code only, never the token.

## Source library

Files arrive through a resumable upload session or a registered connector client, then go through one pipeline in the worker (`python -m astrasync_api.worker`):

1. **Verify:** hash the final assembled bytes, and check size and digests. A failure is quarantined and can't be searched, previewed, downloaded or analysed.
2. **Preserve:** store an immutable master. The same bytes make one artifact and a recorded repeat receipt. A changed file makes a new revision, and old bytes stay retrievable.
3. **Parse:** run the `SourceAdapter` registered for the source type. With none, bytes stay `VERIFIED_BYTES`, the job ends `PARTIAL` with `PARSER_UNAVAILABLE`, and `POST /ingest/ific` can index them later.
4. **Index:** store each record's raw values, exact location and quality findings. Previews read these rows, never the master.

**Three separate states are never merged:** byte integrity (`artifact_integrity_checks`), publisher trust (`publisher_auth_status`) and parse status (`status`). Only a `SourceClient` reporting a signed digest can reach `VERIFIED_PUBLISHER`; a match with a digest supplied alongside a file stays `HASH_MATCH_MANIFEST_UNTRUSTED`.

**Entitlements:** rights on `resource_entitlements` with `object_type=source` and the artifact's classification: `READ`, `DOWNLOAD` and `IMPORT`. `PUBLIC` and `INTERNAL` are open within a tenant; everything else needs one.

**Plugging in components (Data/AI):** set `ASTRASYNC_SOURCE_ADAPTERS` to `module:Class` values, and `ASTRASYNC_SOURCE_CLIENTS` to `endpoint_ref=module:Class` values. See `contract/interfaces.py` and `AdapterRecord`.

## Cases and review

The backend orchestrates. It holds no RF formula, legal limit or AI model.

- **Creating a case:** the relevance pipeline calls `cases.upsert_candidate` with a `CaseCandidate`. A new case is always `INSUFFICIENT_DATA`, whatever the frequency overlap.
- **Analysis (`analysis.py`):** a worker job freezes the scenario and records a row for every candidate method in the catalogue. Methods not registered are `NOT_IMPLEMENTED`. One failing method never hides the others and never yields a number.
- **Margins:** `predicted - limit`, only for a verified upper-bound criterion whose citation, unit, bandwidth, metric and statistics all match. A margin supplied by a resolver is ignored.
- **Findings:** deliberately cautious. Nothing here concludes `NO_IDENTIFIED_CONCERN`, and `METHOD_DISAGREEMENT` needs a per-metric tolerance the docs have not set, so neither is produced yet.
- **Immutability:** method runs, criterion checks and review events are insert-only, enforced by a trigger on PostgreSQL. A rerun creates a new run.
- **Drafts:** agent output is validated like untrusted input: citations must exist, and text making unsupported claims gets a warning. Restricted classifications never reach an agent by default (`ASTRASYNC_AI_CLASSIFICATIONS`). Everything else keeps working without an agent.
- **Decisions:** only `REVIEW_DECIDE` can approve, and an objection needs a verified criterion. Nothing is ever sent automatically.

**Plugging in components (Data/AI):** set `ASTRASYNC_RF_METHODS` to `module:Class` values, and `ASTRASYNC_CRITERION_RESOLVER` and `ASTRASYNC_DRAFT_AGENT` to one each. See `contract/interfaces.py`, `MethodAssessment`, `MethodCalculation` and `AgentDraftResponse`.

## Alerts

The alert engine is its own process (`python -m astrasync_api.alerts`), so an ingest or RF backlog can't delay it.

- **Flow:** durable `outbox_events`, then versioned rules, then one deduplicated alert per rule, then deliveries, then acknowledgment. Each rule decision is audited.
- **Truthful triggers:** an exceedance alert re-checks stored state for a verified criterion and a margin. An event alone can't create one.
- **Safe text:** titles come from fixed templates in `alerts.py`, so rules and source records can't add content. A push carries only `PushPayload`.
- **Recipients:** active users with a routed role who can read the case at that moment. Inbox and deep-link access are re-checked on each request.
- **Delivery states:** in-app, then `PENDING`, `SENT`, `DELIVERED`, `READ` or `FAILED`. `SENT` only means handed to the provider. Without a gateway, push fails visibly with `PUSH_NOT_CONFIGURED`.
- **Limits:** per-user push quota, quiet hours, and channel choices. Critical and security alerts skip the last two.

**Add a provider:** implement `alerts.PushGateway`, and set `ASTRASYNC_PUSH_GATEWAY` and `ASTRASYNC_PUSH_TOKEN_KEY` (a Fernet key).

## Session policy

Tokens are verified on every request, and the database is read each time, so these apply to the user's next request, even with an unexpired token:

| Action | Command | Effect |
| --- | --- | --- |
| Deactivate an account | `deactivate-user` | `403` until reactivated |
| Revoke sessions | `revoke-sessions` | Older tokens get `401`; the user can sign in again |
| Remove a role | `revoke-role` | Capabilities shrink immediately |

There is no self-registration. A valid sign-in with no provisioned account gets `403`. Revoking a single device needs device-bound tokens and arrives with the native clients in Stage 7.

## Settings

| Variable | Required | Notes |
| --- | --- | --- |
| `ASTRASYNC_ENVIRONMENT` | Yes | `DEMO`, `STAGING` or `PRODUCTION` |
| `ASTRASYNC_DATABASE_URL` | Yes | e.g. `postgresql+psycopg://...`. SQLite is refused outside `DEMO` |
| `ASTRASYNC_OIDC_ISSUER` | Yes | Must match the token's `iss` exactly |
| `ASTRASYNC_OIDC_AUDIENCE` | Yes | This API's identifier at the provider |
| `ASTRASYNC_OIDC_JWKS_URI` | Yes | Fixed URI: no discovery, no redirects |
| `ASTRASYNC_OIDC_REQUIRED_SCOPES` | Outside `DEMO` | Comma-separated |
| `ASTRASYNC_OIDC_ALGORITHMS` | No | Default `RS256,ES256` |
| `ASTRASYNC_OIDC_MFA_REQUIRED` | No | Default `true`. Cannot be `false` outside `DEMO` |
| `ASTRASYNC_OIDC_MFA_AMR`, `ASTRASYNC_OIDC_MFA_ACR` | No | Accepted values. Default `amr` of `mfa`. **Check what your provider actually issues** |
| `ASTRASYNC_CORS_ORIGINS` | No | Exact origins, no wildcards |
| `ASTRASYNC_OBJECT_STORE_PATH` | For uploads | Local store, `DEMO` only: refused elsewhere because it has no encryption at rest |
| `ASTRASYNC_MAX_UPLOAD_BYTES` | No | Default 10 GiB |
| `ASTRASYNC_SOURCE_ADAPTERS`, `ASTRASYNC_SOURCE_CLIENTS` | Worker | Comma-separated. See above |
| `ASTRASYNC_RF_METHODS`, `ASTRASYNC_CRITERION_RESOLVER` | Worker | See "Cases and review" |
| `ASTRASYNC_DRAFT_AGENT` | API | Empty means AI drafting is off |
| `ASTRASYNC_AI_CLASSIFICATIONS` | No | Default `PUBLIC,INTERNAL` |
| `ASTRASYNC_BUILD_SHA` | No | Stored on each analysis run for replay |
| `ASTRASYNC_PUSH_TOKEN_KEY` | For device registration | Fernet key that encrypts push tokens at rest |
| `ASTRASYNC_PUSH_GATEWAY` | For push | `module:Class` implementing `alerts.PushGateway` |

With none set, the API starts unconfigured and denies everything. An unsafe or partial configuration refuses to start.

## Commands

Install, from this folder:

```bash
pip install -r requirements-dev.lock
```

```bash
pip install --no-deps -e .
```

Apply migrations, then provision (with `ASTRASYNC_DATABASE_URL` set):

```bash
python -m astrasync_api.admin migrate
```

```bash
python -m astrasync_api.admin create-tenant --tenant MY-TENANT
```

```bash
python -m astrasync_api.admin provision-user --tenant MY-TENANT --issuer https://idp.example --subject USER-SUB --role ANALYST
```

```bash
python -m astrasync_api.admin register-source --tenant MY-TENANT --source-id MY-SOURCE --publisher "Publisher" --domain FINNISH_REFERENCE --source-type M4_ALLOCATION --classification INTERNAL --rights-basis "Basis for access and retention"
```

Run:

```bash
uvicorn astrasync_api.app:create_app --factory
```

Test. By default this uses SQLite; set `ASTRASYNC_TEST_DATABASE_URL` to a **disposable** PostgreSQL database to also exercise the append-only audit trigger. **The tests drop its `public` schema.**

```bash
python -m pytest
```

## Local development stack

`tests/support/dev_stack.py` provides a throwaway identity provider with test personas and no passwords, and runs the API against SQLite with matching accounts and made-up source records, indexed through the real pipeline by a test-only parser. It is not packaged, binds to loopback and works only in `DEMO`. From the repository root, start each in its own terminal:

```bash
traficom-integration/backend/.venv/Scripts/python traficom-integration/backend/tests/support/dev_stack.py idp
```

```bash
traficom-integration/backend/.venv/Scripts/python traficom-integration/backend/tests/support/dev_stack.py api
```

```bash
traficom-integration/backend/.venv/Scripts/python traficom-integration/backend/tests/support/dev_stack.py worker
```

```bash
npm --prefix traficom-integration/ui run dev
```

Then open `http://127.0.0.1:5173`.
