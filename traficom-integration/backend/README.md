# AstraSync backend

FastAPI service. **Status:** IPD stage 1, secure skeleton. Identity, authorization and audit are implemented; apart from `GET /api/v1/me`, every route returns `501` after authorization. MFA, native-client sign-in and the production identity provider have not been tested against a real provider.

## How access works

Each request passes these checks in order, before its body is read:

1. **Token (`oidc.py`):** signature against the provider's published keys, issuer, audience, expiry, required scopes and MFA evidence (`amr` or `acr`). Only asymmetric algorithms are possible.
2. **Identity (`identity.py`):** the issuer and subject must match a provisioned, active user. Roles and tenant always come from the database; those claims in a token are ignored.
3. **Capability (`security.py`):** the role must grant the capability the route declares in the contract. A v1 route cannot be registered without one.
4. **Object (`authz.py`):** **each route that touches a stored object must call `ObjectAccessPolicy`.** It checks tenant, data environment, classification and source entitlement, and answers a denial with the same `404` as a missing object. No stored-object route exists yet, so its route-level use starts in Stage 2.

Denied actions, permitted writes, and exports and downloads are recorded in `audit_events`. A write, export or download that cannot be audited does not proceed. Rejected tokens are logged with a reason code only, never the token.

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

Run:

```bash
uvicorn astrasync_api.app:create_app --factory
```

Test. By default this uses SQLite; set `ASTRASYNC_TEST_DATABASE_URL` to a **disposable** PostgreSQL database to also exercise the append-only audit trigger. **The tests drop its `public` schema.**

```bash
python -m pytest
```

## Local development stack

`tests/support/dev_stack.py` provides a throwaway identity provider with test personas and no passwords, and runs the API against SQLite with matching accounts. It is not packaged, binds to loopback and works only in `DEMO`. From the repository root, start each in its own terminal:

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
