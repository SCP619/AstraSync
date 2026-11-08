# Security and privacy

**Identity and sessions**
- OIDC bearer tokens are verified against the provider's keys: issuer, audience, scope and MFA.
- Users are matched by issuer plus subject, never by email.
- Roles and tenant come from the database, never from the token.
- Deactivation and session revocation apply on the next request.

**Authorization**
- Deny by default. Each route declares a capability, and the server enforces it.
- Tenant isolation, data classification and source entitlements filter every list, search,
  finding, analysis and export.
- IFIC findings require READ on the issue and on every reference source used, so restricted
  reference data cannot surface through a less restricted issue.
- Administrators get no content access and cannot change their own access.
- All writes and denials are audited in an append-only audit trail.

**Acquisition and parsing**
- Downloads only over HTTPS from allow-listed hosts, with no redirects and a size limit.
- Every file is hashed with SHA-256 and kept as an immutable original.
- Archive limits apply to member count, names, size and compression ratio.
- Parsers run in a separate process with memory and time limits. Unreadable files are quarantined.

**Clients**
- Tokens are held in memory only.
- The judge demonstration is synthetic, makes no API calls and grants nothing.

**AI**
- The model runs locally (n8n → Ollama), restricted to loopback destinations.
- An AI classification policy controls what may reach it, and replies pass grounding checks.
- See [`AI_WORKFLOW.md`](AI_WORKFLOW.md).

**Repository hygiene**
- Secrets live in git-ignored local files.
- CI runs gitleaks secret scanning, pip-audit and npm audit, and produces SBOMs.

**This package**
- No credentials, tokens, `.env` files, databases or raw IFIC/M4/workbook inputs.
- The results contain only derived values: notice data published by ITU, and labels of the
  synthetic workbook stations (for example "Station 615366 TX") supplied by the organizers.
- It was checked for secrets before release (`SUBMISSION_MANIFEST.json`, `security_checks`).

**Not production-ready**
- TLS and encryption at rest are deployment work.
- There is no production identity provider, signed release packages or threat model yet.
