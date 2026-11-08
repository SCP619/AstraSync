# Demo access

## A. Judge demonstration (no backend, synthetic data)

Not hosted yet (a static deployment is configured in `traficom-integration/ui/vercel.json` but no
public URL exists). Run it locally:

```powershell
npm --prefix traficom-integration\ui ci
```

```powershell
npm --prefix traficom-integration\ui run dev
```

Open http://127.0.0.1:5173/demo (or the sign-in page's "View the judge demonstration" link). It
reads only the bundled `src/demo/judge-demo.json` and makes no API calls.

## B. Full application (real data)

Requirements and installation: [`../05_Code_Repository/INSTALLATION_GUIDE.md`](../05_Code_Repository/INSTALLATION_GUIDE.md).

1. Optional port overrides (if Windows reserves 8800/8801) and the real-source switch in the
   git-ignored `traficom-integration/backend/dev_stack.local.env`:

   ```
   ASTRASYNC_DEV_API_PORT=18800
   ASTRASYNC_DEV_IDP_PORT=18801
   ASTRASYNC_DEV_REAL_SOURCES=1
   ```

   and the same ports in `traficom-integration/ui/.env.development.local`
   (`VITE_API_BASE_URL`, `VITE_OIDC_AUTHORITY`).
2. Start the identity provider, API and worker:

   ```powershell
   traficom-integration\backend\.venv\Scripts\python traficom-integration\backend\tests\support\dev_stack.py all
   ```

3. Start the UI: `npm --prefix traficom-integration\ui run dev`, open http://127.0.0.1:5173.
4. Load real data: sign in as **Administrator, tenant A**, Source library → check
   `TRAFICOM-M4`, then `ITU-TERRESTRIAL-IFIC` and `ITU-SPACE-IFIC` (dev issue ranges 3075–3076 and
   3073–3074). Sign in as **Analyst, tenant A** and upload the challenge workbook to
   `CHALLENGE-WORKBOOK`. Space 3074 takes about 3 minutes to parse. Upload the workbook before the
   IFIC checks so the analyses use it. Stored analyses are not recomputed when the code changes:
   if the dev database was filled by an older version (no border screening or criterion panel),
   stop the stack, delete `traficom-integration\backend\.dev\` and load again.
5. Optional local AI: n8n with the workflow in `traficom-integration/n8n/` and Ollama `qwen3:8b`,
   configured as in `docs/operations/N8N_LOCAL_AI.md`. Without it, drafting uses the deterministic
   agent.

Personas (development only, no passwords): Analyst, Reviewer, Administrator and Demo viewer of
tenant A; Analyst of tenant B; plus personas for no role, no account, no MFA and expired tokens.
