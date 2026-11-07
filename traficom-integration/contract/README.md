# AstraSync API contract

**Version:** `1.0.0-draft.5` · **Status:** `PROPOSED`: needs approval from both contributors (IPD stage 0, TRD section 15.1). Each operation's `x-implementation-status` says whether it is `IMPLEMENTED` or still `DESIGNED`.

The Pydantic models in `backend/astrasync_api/contract/` are the source. Everything else is generated from them and checked for drift.

| File | Purpose |
| --- | --- |
| `backend/astrasync_api/contract/` | Models, status vocabularies, role capabilities, worker and agent interfaces |
| `contract/openapi.json` | Generated OpenAPI 3.1 spec, including event and worker payloads |
| `contract/fixtures/valid/` | Payloads both backend and UI must accept |
| `contract/fixtures/invalid/` | Payloads the backend must reject |
| `ui/src/api/schema.gen.ts` | Generated TypeScript types |
| `ui/src/api/__contract__/` | Generated fixtures checked against those types, plus compile-time negative tests |
| `contract/DECISIONS.md` | Documentation conflicts resolved here, and assumptions to review |

## Conventions

- **Fixtures:** named `<ModelName>.<case>.json`. They are hand-made and synthetic, never copied from the Traficom workbook or ITU data. Numbers in them are schema examples, not calculations.
- **Units:** in the field name: `_mhz`, `_hz`, `_db`, `_m`, `_deg`, `_bytes`, `_seconds`. Metric results also carry an exact `unit` string.
- **Time:** `_utc` fields are ISO 8601 and must be UTC.
- **Missing values:** `null`, never zero. Response fields are always present.
- **Unknown fields:** rejected in both directions.
- **Errors:** always `{ "error": { "code", "message", "details", "request_id" } }`.
- **Authorization:** each operation declares `x-required-capability`. A capability is necessary but not sufficient: tenant, classification, source entitlement and case access are checked per object. For an unentitled object, answer `404`, so that its existence does not leak.
- **Retried writes:** operations with side effects require an `Idempotency-Key` header.

## Change and check commands

Run from `traficom-integration/backend/`, after `pip install -e .[dev]`:

```bash
python -m astrasync_api.contract.export
```

```bash
python -m pytest
```

Then from `traficom-integration/ui/`, after `npm ci`:

```bash
npm run contract:generate
```

```bash
npm run contract:check
```

A contract change also needs the matching BSD update and cross-review.
