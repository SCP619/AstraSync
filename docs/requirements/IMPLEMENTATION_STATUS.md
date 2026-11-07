# AstraSync implementation status

Last updated: 2026-11-07. Update this file in the PR that changes the status. Read it first in a new session.

**Requirements source.** The v3 documentation (PRD, TRD, IPD, quality charter, architecture) is not in this repository; `docs/requirements` and `docs/architecture` were empty. It is kept outside the repo at `Since_AI_Traficom/Since_AI_Traficom/AstraSync_documentation_v3/AstraSync/docs/` on the development machine. Contract decisions and deviations are in [`traficom-integration/contract/DECISIONS.md`](../../traficom-integration/contract/DECISIONS.md).

**Status words.** *Verified*: an automated test or recorded device run shows it. *Synthetic only*: verified only on challenge or made-up data. *Not started*, *Blocked*: as stated, with the reason.

## Stage status

| Stage | Status | Evidence | What is missing |
| --- | --- | --- | --- |
| 0 Contract | Verified | Contract tests in CI; OpenAPI `1.0.0-draft.5` | BSD update for DECISIONS entries |
| 1 Secure skeleton | Verified on the local test IdP | Backend auth/authorization tests, deny-by-default | Real identity provider (TRD §18) |
| 2 Source library | Verified, synthetic only | Upload, immutable archive, integrity, index, preview, search, RBAC tests. **AT-H-01**: real workbook SHA-256 `bb7f481f…` and 874 rows reconciled through the pipeline (`test_traficom_ingest.py`, run locally with the file; the file is not in git) | Authorised ITU connectors, source monitoring, real-format adapters (blocked, see below) |
| 3 Space RF | In progress | `SPACE_PFD_FREE_SPACE` (`astrasync_physics.space_pfd`): Tier 1 validation against 40-digit reference values, linear vs dB agreement, the −6.02 dB doubling rule, refusal of missing and invalid inputs; runs through the real analysis runner with no margin and no criterion | Directional/time-series PFD, EPFD, criterion resolver with cited limits, the notice-to-scenario mapping (needs real IFIC data) |
| 4 Terrestrial RF | Not started | | Two real IFIC issues, P.1546 if validated |
| 5 Case UI and evidence | Verified with demo plugins | Case workflow, reviewer API, inspector, 91 UI tests | Real relevance detection, RF methods and AI agent wired in |
| 6 Large data | Not started | | 4/10 GB benchmarks, 10M/50M rows, recovery report |
| 7 Native and alerts | Verified on devices (PR #7) | Windows W1–W3, W5–W12 automated on the CI package; W4 by hand; Android A1–A8 automated on an Android 15 emulator | Android push (no gateway), signed packages |
| 8 Security and operations | Not started | | Scans, backups, monitoring, sandboxed parsing (A16) |
| 9 Extended methods | Not started | | P.1812/P.452, NGSO, EPFD |
| 10 Optional | Not started | | |

## Backlog, in dependency order

1. **Traficom workbook parser**: done in `astrasync-core-lib` (`astrasync_data.traficom_workbook`). Clean, flagged and blocked counts: 868 valid, 3 with warnings, 1 needs review, 2 insufficient data. The v3 audit's counts were partly wrong (DECISIONS D11).
2. **Stage 3 baseline space PFD.** Free-space PFD from EIRP and distance, as an `RFMethod` plugin with hand-checked and independently computed vectors. It needs notice inputs, which come from real IFIC data (blocked). It can be validated and wired in with labelled synthetic notices.
3. **Criterion resolver** with cited, edition-dated limits (ITU Radio Regulations). No threshold may be entered without its source document and table reference. Until then a margin stays null.
4. **Finland relevance**: frequency matching of notices against the reference stations (needs item 2's notice model).
5. **Stage 6 benchmarks**: synthetic scale generator (tens of millions of rows, labelled), 4/10 GB resumable ingest and recovery report. Independent of external access.
6. **Stage 8 hardening**: CI security scans, dependency and licence checks, parser sandboxing, backups/restore drill.
7. **Stage 4 terrestrial and Stage 9 methods**: need real IFIC issues and validated reference implementations.

## Blockers

| Blocker | Affects | Needed |
| --- | --- | --- |
| No authorised ITU BR IFIC sample or access route in hand | Stage 2 connectors, 3, 4, 9; AT-H-03/04 | An authorised IFIC file and its terms (TRD §18) |
| Challenge brief section 05 links not yet reconciled | Connectors | The brief PDF is in the challenge folder; read section 05 before building connectors |
| No Lovable project for AstraSync | Planned Lovable UI work | The connected Lovable account (workspace "My Lovable") has one unrelated project from 2025 and no GitHub link. Creating a project spends credits and imports code; needs approval and a sync plan. No Lovable operation has been run |
| `LICENSE.md` calls `astrasync-core-lib` background IP, while the docs say a folder name doesn't establish that | Code added to `astrasync-core-lib` | Team and legal decision; the licence was not changed |
| Android push gateway | Stage 7 push | Firebase project or another approved gateway |

## Machine set-up notes

- GitHub: commit as `SCP619` through the `github-scp619` SSH alias. `gh` is at `C:\Program Files\GitHub CLI\gh.exe` if it isn't on PATH.
- Android: JDK 21, the SDK in `%LOCALAPPDATA%\Android\Sdk` and emulator `astrasync-e2e`. Windows Hypervisor Platform is on.
- No Rust or Visual Studio Build Tools, so Windows packages come from CI.
- The real workbook lives outside the repo. Point `ASTRASYNC_TRAFICOM_WORKBOOK` at it to run the golden tests.
