# AI workflow: AstraSync Intelligence

All analysis in this package is deterministic. AI is used only to word correspondence drafts and
to answer questions about a case, from evidence AstraSync has already computed and authorized.

```
User (signed in) ─▶ AstraSync API: authorization, AI classification policy,
                    builds the case evidence (stored, immutable, permission-checked)
   ─▶ local n8n webhook (header secret, loopback only) ─▶ Basic LLM Chain ─▶ Ollama qwen3:8b (same PC)
   ◀─ {"text": …}
   ─▶ grounding checks ─▶ draft stored for expert review / answer shown
```

**Grounding checks** (`astrasync_api/drafting.py`). The reply is refused unless:
- every cited `[E:evidence_id]` exists in the case evidence;
- every number in the text appears in the evidence (rounding allowed);
- the text does not assert interference, a violation or non-compliance.

A refused reply is retried once with the reason; if it is refused again, nothing is stored and the
API returns 503.

**Prompt injection.** Notice text from publications is passed only inside a JSON evidence block
that the instructions declare to be data. The checks above do not depend on the model obeying.

**Locality and data policy.**
- The transport accepts only loopback destinations, refuses redirects and limits request and reply
  sizes.
- The secret stays on the server; clients never see it.
- Only classifications listed in `ASTRASYNC_AI_CLASSIFICATIONS` (default PUBLIC, INTERNAL) may
  reach the model.
- n8n never queries AstraSync; it does not save execution data.

**Human control.** Drafts are always `requires_human_review`; nothing is sent automatically. A
deterministic drafting agent (no model) produces the same structure when no local model is
available.

**Verified 2026-11-08 (live, this PC).**
- Unauthenticated webhook calls were refused with no model call.
- Over 8 draft runs, 6 were accepted and 2 were refused for wrong citations (the intended
  behaviour).
- Draft plus question passed 3 of 3 runs with the retry.
- Each draft takes 2–3 minutes on `qwen3:8b`.

Setup and the workflow export: `docs/operations/N8N_LOCAL_AI.md` and
`traficom-integration/n8n/astrasync-local-llm-webhook.json` (credential names only) in the
repository.
