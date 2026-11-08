# Test results

All results below are from runs that actually completed; none is extrapolated.

## CI on the code baseline `8e0f105` (`main`, GitHub Actions run 42458906251, 2026-11-08)

| Suite | Result |
| --- | --- |
| Core library (parsers, analysis, P.1546, PFD, border screening): ruff, format check, mypy strict, pytest | 133 passed, 13 skipped (real-data tests need inputs not in CI) |
| Backend: ruff, mypy, OpenAPI contract check | Clean |
| Backend pytest on SQLite | 466 passed, 9 skipped |
| Backend pytest on PostgreSQL | 472 passed, 3 skipped |
| UI: contract check, typecheck, vitest, production build | 119 tests passed (11 files), build passed |
| Supply chain (gitleaks secret scan, pip-audit, npm audit, SBOMs) | Passed |

PR #30 (merged as this baseline) also passed the Windows and Android compile checks and the
packaged Windows and Android test builds (8/8 checks).

## Real-data and live checks (local, 2026-11-08)

| Check | Result |
| --- | --- |
| P.1546-6 vs ITU-R WP 3K reference (54 cases) | All within 0.01 dB; maximum 5.1×10⁻⁵ dB |
| Space 3074 / Terrestrial 3076 parsing with the official files | 196/196 notices kept; 3076 matches ITU's per-part counts |
| Reproduction of both evaluations from `8e0f105` | Identical results (see `04_Input_Output/REPRODUCIBILITY.md`) |
| Live platform pipeline (dev stack): M4, workbook, IFIC 3073–3076 acquired, parsed, analysed | 0 records rejected; results equal to the offline evaluation (run before the border-screening release; re-run needs a fresh dev database) |
| Local AI end to end (n8n → Ollama) | See `AI_WORKFLOW.md` |
| Browser check: sign-in, dashboard, IFIC issues, findings detail, case analysis and draft | Passed |

Device runs of the Windows and Android packages were recorded on 2026-11-07
(`traficom-integration/ui/DEVICE_TESTING.md`).
