# AstraSync backend

FastAPI service. **Status:** IPD stage 2. Identity, authorization, audit and the source library are implemented. Each operation's `x-implementation-status` in `contract/openapi.json` says what is real; other routes return `501` after authorization. MFA and the production identity provider have not been tested against a real provider. Object storage is local and demo-only; real ITU and workbook parsers and connectors do not exist yet.

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
npm --prefix traficom-integration/ui run dev
```

Then open `http://127.0.0.1:5173`.
