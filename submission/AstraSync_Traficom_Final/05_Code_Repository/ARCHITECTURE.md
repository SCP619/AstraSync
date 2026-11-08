# Architecture

| Layer | Location | Technology | Responsibility |
| --- | --- | --- | --- |
| Clients | `traficom-integration/ui` | React 18 + TypeScript (Vite); Tauri 2 (Windows); Capacitor 7 (Android) | One UI for all platforms; holds no RF logic, permissions or stored tokens |
| API | `traficom-integration/backend/astrasync_api` | Python 3.11, FastAPI, SQLAlchemy, Alembic | OIDC bearer tokens, deny-by-default authorization, sources, records, cases, drafts, reviews, alerts, IFIC analyses |
| Worker | same package (`worker.py`) | Durable jobs with leases and retries | Discovery, download, parsing (isolated process), indexing, RELEVANCE (issue analysis), RF analysis runs |
| Science and parsers | `astrasync-core-lib` | Pure Python plugins | IFIC/M4/workbook parsers, Finland relevance, border screening, P.1546-6, space PFD |
| Contract | `traficom-integration/contract` | Pydantic → OpenAPI → TypeScript | One typed contract for server and clients |
| Storage | — | PostgreSQL (SQLite in dev/tests); file object store; Parquet + DuckDB | Metadata, access, jobs, append-only audit; immutable originals; parsed records |
| Local AI | `traficom-integration/n8n`, `astrasync_api/drafting.py` | n8n webhook → Ollama (`qwen3:8b`) on the same machine | Wording of drafts and answers only, checked for citations, numbers and claims |

Extensibility (judging criterion B): sources, parsers, RF methods, criterion resolvers and drafting
agents are plugins named in server settings. The terrestrial side quest reuses the same
acquisition, storage, case, review and drafting machinery as space, adding only its parser,
P.1546-6, border screening and the T/R 25-08 criterion set. A new IFIC issue needs no code change.

Key decisions (repository: `docs/ARCHITECTURE_DECISIONS.md`, `traficom-integration/contract/DECISIONS.md`,
`docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md`):

- Server-side authorization is authoritative: tenant, classification and source entitlements on
  every list, search, finding and export.
- Originals are immutable and hashed; outages are never read as withdrawals.
- Nothing missing is defaulted; synthetic data is labelled synthetic.
- Every calculation records method, version, implementation hash, inputs, assumptions and
  validation status.
- No regulatory finding without a cited criterion; frequency overlap is never called interference.
- AI never sends anything and never decides; an expert approves every draft.
