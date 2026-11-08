# AstraSync operations runbook

Last updated: 2026-11-07. Covers the API, the worker, the database, object storage and the
record store. Commands run from `traficom-integration/backend` with the service's environment.
Anything marked **not built** must be provided by the deployment.

## 1. Components and settings

| Component | Start | Required settings |
| --- | --- | --- |
| API | `uvicorn astrasync_api.app:create_app --factory` | `ASTRASYNC_ENVIRONMENT`, `ASTRASYNC_DATABASE_URL`, `ASTRASYNC_OIDC_ISSUER`, `ASTRASYNC_OIDC_AUDIENCE`, `ASTRASYNC_OIDC_JWKS_URI`, `ASTRASYNC_CORS_ORIGINS` |
| Worker | `python -m astrasync_api.worker` (`--once` drains and exits) | Database URL, `ASTRASYNC_OBJECT_STORE_PATH`, adapters, clients, methods |
| Record store | Shared directory for API and worker | `ASTRASYNC_RECORD_STORE_PATH` |
| Parser isolation | Always on outside DEMO | `ASTRASYNC_PARSER_MEMORY_MB` (2048), `ASTRASYNC_PARSER_TIMEOUT_SECONDS` (3600) |
| Criteria | Only cited, approved entries | `ASTRASYNC_CRITERIA_REGISTRY` with `ASTRASYNC_CRITERION_RESOLVER=astrasync_api.criteria:RegistryCriterionResolver` |

Settings refuse unsafe combinations at start: plain-HTTP identity endpoints off loopback, MFA
off or the local object store outside DEMO, in-process parsing outside DEMO, wildcard CORS.

**Not built:** TLS termination, encryption at rest for the database, object store, record store
and backups (TR-SEC-001), and container/OS confinement of parser processes.

## 2. Health and monitoring

- `GET /healthz`: the process is up. `GET /readyz`: the database answers (503 otherwise).
  Neither needs a token or reveals anything else. Use them for liveness and readiness probes.
- `GET /api/v1/operations/metrics` (capability `JOB_READ`, per tenant): queue backlog per lane
  and status with the oldest job's age, failed jobs in 24 h, pending outbox events, record-store
  datasets/records/bytes.
- Alert on: oldest `QUEUED`/`RETRYING` age above the expected cadence; any rise in
  `failed_jobs_last_24h`; `outbox_pending` growing between scrapes; `/readyz` failing.
- Source freshness and failures: `GET /api/v1/sources/{id}/health` and source-health alerts.

**Not built:** time-series export (Prometheus/OpenTelemetry) and log shipping.

## 3. Routine tasks

| Task | Command |
| --- | --- |
| Apply migrations | Run automatically by the API at start; `alembic upgrade head` equivalent through `db.run_migrations` |
| Build record datasets after enabling the record store | `python -m astrasync_api.records_cli build` |
| Verify every record dataset | `python -m astrasync_api.records_cli verify` (exit 1 on any damage) |
| First administrator of a tenant | `python -m astrasync_api.admin provision-user --tenant <t> --issuer <iss> --subject <sub> --role ADMINISTRATOR` (no self-registration, no automatic administrator) |
| Users, roles, sessions, source entitlements | **Users and access** screen (`/admin/users`, `ADMIN_USERS`); CLI fallback `deactivate-user`, `revoke-sessions`, `revoke-role` |
| Fetch new IFIC issues | Check `ITU-SPACE-IFIC` / `ITU-TERRESTRIAL-IFIC` in the source library (or set a poll interval on the connector); ranges `ASTRASYNC_ITU_SPACE_ISSUES`, `ASTRASYNC_ITU_TERRESTRIAL_ISSUES` |
| Re-run an issue analysis | Delete its `ific_analyses` row and queue `ific_pipeline.enqueue_relevance` for the artifact; the analysis is deterministic for the same references |
| Evaluate an issue offline | `python -m astrasync_data.ific_evaluate space|terrestrial --issue … --previous … --m4 … --workbook … --out …` |
| Back up | `python -m astrasync_api.backup create <empty dir>` |
| Check a backup | `python -m astrasync_api.backup verify <dir>` |
| Restore drill | Point the settings at an **empty** database and empty stores, then `python -m astrasync_api.backup restore <dir>` |

Restore re-hashes every master against its recorded SHA-256 and every dataset against its
manifest, and checks row counts; it stops on the first difference. Run a drill at least before
each release and after any storage change, and record the output.

Backups contain restricted source bytes, audit history and encrypted device tokens. Keep them
under the same access control and encryption as production. For large PostgreSQL deployments
use native `pg_dump`/point-in-time recovery for the database, keep the masters and datasets in
versioned object storage, and still run `backup verify`/`records_cli verify` as the integrity
check.

## 4. Incidents

| Symptom | Meaning | Action |
| --- | --- | --- |
| Job stays `RUNNING`/`VERIFYING` after a worker died | The lease (5 min) has not expired | Wait for reclaim; a new worker resumes it (measured: L1, 301.7 s) |
| Job `FAILED` with "Worker stopped during the final attempt" | Three attempts died | Inspect worker logs; re-trigger ingest after the cause is fixed |
| Artifact `QUARANTINED`, check `FORMAT_PARSER` = `ParserLimitExceeded` | Parser hit the memory or time limit | Treat the file as unsafe. Raise limits only after reviewing the file and source |
| `FORMAT_PARSER` = `ParserRefused` | The adapter rejected the file | Check the source format; never edit the master |
| Record API returns 500 for one artifact; `records_cli verify` reports DAMAGED | Dataset file differs from its manifest | Restore the dataset from backup, or delete its manifest row and rebuild with `records_cli build` |
| `/readyz` 503 | Database unreachable | Check database health and credentials; the API refuses work meanwhile |
| Signed-in user gets 403 `USER_NOT_PROVISIONED` | No user with this token's issuer plus subject (often the IdP issuer URL changed) | Provision the identity under the issuer in the token; never match on email |
| Space IFIC parse fails with `ParserLimitExceeded` (memory) | The SNS database is ~300 MB unpacked | Raise `ASTRASYNC_PARSER_MEMORY_MB` (6144 is enough for 3074) |
| RELEVANCE job `PARSER_UNAVAILABLE` | No adapter for the IFIC, M4 or workbook source type | Configure `ASTRASYNC_SOURCE_ADAPTERS` |
| Source health stale | Publisher unreachable or changed | Outages never count as withdrawals; follow `MANUAL_REQUIRED` steps |

## 5. Security notes

- Never put secrets in settings files committed to Git; CI runs gitleaks over the full history.
- Dependency audits and SBOMs: `.github/workflows/supply-chain.yml` (weekly and on every PR).
- Release packages are unsigned until signing keys are provided (TR-SEC-006).
- Restricted data must not be sent to Lovable or any AI provider outside
  `ASTRASYNC_AI_CLASSIFICATIONS`.
