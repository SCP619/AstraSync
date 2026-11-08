# Prompt for a new Claude Code session

Start Claude Code in the repository root (the folder with `docs/`, `traficom-integration/` and
`astrasync-core-lib/`), then paste:

---

You are continuing development of AstraSync as its engineer. I am SCP619. This is a different
Windows PC from the one used so far.

1. Read `docs/NEW_PC_HANDOFF.md`, then `docs/WINDOWS_DEVELOPMENT_SETUP.md`, then
   `docs/REQUIREMENTS_MATRIX.md`, `docs/DEVELOPMENT_PROGRESS.md` and
   `docs/ARCHITECTURE_DECISIONS.md`.
2. Inspect the real state: `git status`, `git log -5`, branches, open PRs and CI on `main`
   (`gh` CLI). Treat the handoff as a snapshot, not as current truth.
3. Verify the Git identity and remote: `git config user.name` = `SCP619`, `user.email` =
   `priyoshaktiman@gmail.com`, `origin` = `git@github-scp619:SCP619/AstraSync.git`, and
   `ssh -T git@github-scp619` greets SCP619. If any of these is wrong, stop and tell me.
4. Check which tools, local settings and data exist on this PC (setup guide sections 1, 6 and 9).
   Local files do not travel with Git: the challenge workbook, IFIC downloads and the P.1546
   reference may be missing. Report what is missing; do not download or copy anything restricted
   without asking.
5. Set up only what is missing, following the setup guide, without changing tracked files for
   machine-specific values (use the git-ignored local files for ports).
6. Run a targeted smoke test (setup guide section 10) and report the actual results.
7. Tell me which functionality works on this PC and which needs data or tools that are absent.
8. Then wait for my instruction. When asked to develop, continue unfinished requirements from the
   matrix and the handoff; do not redo completed work.

Rules:
- Never assume local files came with Git.
- Never fabricate scientific data, regulatory limits, citations or results; synthetic data stays
  labelled synthetic.
- Never bypass or weaken authorization, tenant or entitlement checks.
- Never use or copy from `AstraSync-scp619/`; it is an obsolete backup.
- Never duplicate completed work or rewrite the existing architecture without a reason.
- Never claim tests passed without running them, and report failures as they are.
- Commit and push only as SCP619 through `github-scp619`, on `scp619/*` branches with PRs to
  `main`; never another GitHub identity, no Claude co-author or attribution lines, no force-push.

---
