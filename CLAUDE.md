# AstraSync: instructions for Claude Code

Start here: `docs/NEW_PC_HANDOFF.md` (state and map), `docs/WINDOWS_DEVELOPMENT_SETUP.md` (setup),
`docs/REQUIREMENTS_MATRIX.md`, `docs/DEVELOPMENT_PROGRESS.md`, `docs/ARCHITECTURE_DECISIONS.md`,
`traficom-integration/contract/DECISIONS.md`.

- Source of truth: `traficom-integration/`, `astrasync-core-lib/`, `docs/`, `evaluation/`.
  `AstraSync-scp619/` is an obsolete backup: never read from it or add it to Git.
- Git: author, committer and pusher SCP619 `<priyoshaktiman@gmail.com>` via the SSH alias
  `github-scp619`; `scp619/*` branches; PRs to `main`; no force-push; no Claude co-author or
  attribution lines (`.claude/settings.local.json` turns them off, per machine).
- Machine-specific values (ports, real-source switch) go in the git-ignored
  `traficom-integration/backend/dev_stack.local.env` and `traficom-integration/ui/.env.development.local`.
- Never invent RF results, regulatory limits, citations or source data. Frequency overlap is not
  interference; no regulatory finding without an approved criterion; space PFD here is an upper
  bound, not EPFD.
- Server-side authorization is authoritative: deny by default, tenant, classification and source
  entitlements everywhere.
- After changing contract models: `python -m astrasync_api.contract.export` and
  `npm run contract:generate`. Before pushing: backend `ruff check .`, `mypy`, `pytest`; core
  `ruff check .`, `ruff format --check .`, `mypy`, `pytest`; UI `npm run contract:check`,
  `npm test`, `npm run build`.
