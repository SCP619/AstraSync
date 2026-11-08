# Local AI: AstraSync → n8n → Ollama

Protected evidence never leaves the machine: the AstraSync backend (after authentication,
authorization and the `ASTRASYNC_AI_CLASSIFICATIONS` policy) posts a trusted prompt to a local
n8n webhook, n8n runs the model on local Ollama, and the backend checks the reply (citations,
numbers, claims) before storing a draft for expert review. n8n never reads AstraSync data itself.

```
UI ──OIDC──▶ AstraSync API ──X-AstraSync-Secret──▶ n8n webhook ──▶ Basic LLM Chain ──▶ Ollama (qwen3:8b)
                 ▲  grounding checks, audit                                   │
                 └────────────────────────── {"text": "..."} ◀────────────────┘
```

## Workflow

| Item | Value |
| --- | --- |
| Workflow | `AstraSync — Local LLM Webhook`, id `3Y7v8QfhbWVpq6KG` (this instance) |
| Export | [`traficom-integration/n8n/astrasync-local-llm-webhook.json`](../../traficom-integration/n8n/astrasync-local-llm-webhook.json) (credential names only, no secrets) |
| Production URL | `POST http://localhost:5678/webhook/astrasync-llm` (the test URL `/webhook-test/...` works only while the editor listens) |
| Authentication | Header Auth credential, header `X-AstraSync-Secret` |
| Request | `{"system": str, "user": str, "model": str}` (the model field is informational; the Ollama node fixes `qwen3:8b`) |
| Response | `{"text": str}` via Respond to Webhook (`={{ { text: $json.text } }}`) |
| Model | Ollama `qwen3:8b`, thinking off, credential "Ollama account" (base URL not read; reachable from n8n, which runs natively on this PC, not in Docker) |
| Execution data | Success and error runs not saved, progress not saved, timeout 180 s |

## Verified on 2026-11-08 (n8n MCP)

- Manual execution 15: Webhook → Basic LLM Chain → Ollama → Respond to Webhook all succeeded;
  synthetic prompt returned `{"text": "Hello, AstraSync!"}` in 12.9 s.
- Published: active version `6f6b9f94-3fd6-411c-934d-e68326ff2e6f`.
- Production webhook without the header, and with a wrong header: HTTP 403 "Authorization data
  is wrong!" in about 15 ms; no execution was created, so the model was not invoked.
- A request with the correct secret was **not** sent by Claude Code: the secret is a credential
  value and was not read. Run the check below.

Root cause of the earlier failures: the workflow was inactive, so only the test URL existed, and
it stops listening after one call (later calls gave 404). The node graph itself was correct.

## Backend configuration (git-ignored)

In `traficom-integration/backend/dev_stack.local.env`:

```
ASTRASYNC_DEV_LLM_N8N_URL=http://127.0.0.1:5678/webhook/astrasync-llm
ASTRASYNC_DEV_LLM_N8N_SECRET=<the Header Auth credential value>
# optional: ASTRASYNC_DEV_LLM_MODEL=qwen3:8b
```

The dev stack then sets `ASTRASYNC_DRAFT_AGENT=astrasync_api.drafting:GroundedLlmDraftAgent`,
`ASTRASYNC_LLM_PROVIDER=n8n`, `ASTRASYNC_LLM_N8N_URL`, `ASTRASYNC_LLM_API_KEY` and
`ASTRASYNC_LLM_MODEL`. Outside the dev stack set those variables directly.

Transport rules (`astrasync_api.drafting.n8n_transport`):

- destination must be http(s) on `127.0.0.1`, `localhost` or `::1`; a container host name must be
  listed in `ASTRASYNC_LLM_N8N_ALLOWED_HOSTS`; URLs with credentials are refused;
- redirects refused; request ≤ 512 KiB, reply ≤ 256 KiB; timeout
  `ASTRASYNC_LLM_TIMEOUT_SECONDS` (default 120);
- non-200, non-JSON or a reply without a non-empty `text` → `LlmTransportError` → API 503
  `AI_UNAVAILABLE`; errors never contain the secret or the prompt;
- the secret is server-side only; the UI, Android and Windows clients never see it.

## User-side check with the real secret (PowerShell)

```powershell
$secret = Read-Host -AsSecureString "X-AstraSync-Secret"
$plain  = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret))
$body   = '{"system":"Reply with one short sentence.","user":"Synthetic test for AstraSync.","model":"qwen3:8b"}'
Invoke-RestMethod -Method Post -Uri http://localhost:5678/webhook/astrasync-llm `
  -Headers @{ "X-AstraSync-Secret" = $plain } -ContentType "application/json" -Body $body
```

Expected: an object with a `text` property. Then start the dev stack with the two
`ASTRASYNC_DEV_LLM_*` lines and create a draft on a case in the Cases workspace; a refused
model output appears as "The drafting service did not return a usable draft".

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| 404 on `/webhook/astrasync-llm` | Workflow not published. Publish it (n8n UI or MCP `publish_workflow`). |
| 404 on `/webhook-test/...` | Test listener closed; click "Listen for test event" again or use the production URL. |
| 403 | Missing or wrong `X-AstraSync-Secret`. |
| 500 / empty reply | `body.user` missing or not JSON (`Content-Type: application/json`), or Ollama down: `curl http://127.0.0.1:11434/api/tags`. |
| Very slow first reply | Ollama loading `qwen3:8b` into memory (about 5 GB). |
| n8n in Docker | `localhost` in the Ollama credential is the container; use `http://host.docker.internal:11434`. |
| No execution history | Intended: prompts may hold protected evidence. For debugging set "Save successful executions" temporarily in the workflow settings, then turn it off. |
