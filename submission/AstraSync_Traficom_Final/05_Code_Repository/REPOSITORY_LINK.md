# Code repository

| Item | Value |
| --- | --- |
| Repository | https://github.com/SCP619/AstraSync (**private**: the organizers need to be granted read access by the owner, SCP619) |
| Branch | `main` |
| Code baseline of the results | `8e0f10535850d604911c430a8dc640ea960c925a` (merge of PR #30) |
| Submission package | `submission/AstraSync_Traficom_Final/` on `main` (added after the baseline; documentation and copies of the verified outputs only, no code changes) |
| SSH clone (owner) | `git clone git@github-scp619:SCP619/AstraSync.git` (alias for `git@github.com:SCP619/AstraSync.git`) |
| HTTPS clone (invited reviewers) | `git clone https://github.com/SCP619/AstraSync.git` |

Layout: `traficom-integration/backend` (FastAPI API, worker, contract), `astrasync-core-lib`
(parsers, analysis, RF methods), `traficom-integration/ui` (React UI for web, Windows/Tauri,
Android/Capacitor), `traficom-integration/n8n` (local AI workflow export), `evaluation/` (results),
`docs/` (requirements matrix, decisions, architecture, operations). `AstraSync-scp619/` in some
local copies is an obsolete backup and is not part of the repository.

| Task | Command (PowerShell, repository root) |
| --- | --- |
| Install | [`INSTALLATION_GUIDE.md`](INSTALLATION_GUIDE.md) |
| Start backend (IdP, API, worker) | `traficom-integration\backend\.venv\Scripts\python traficom-integration\backend\tests\support\dev_stack.py all` |
| Start frontend | `npm --prefix traficom-integration\ui run dev` → http://127.0.0.1:5173 |
| Backend tests | `cd traficom-integration\backend; .venv\Scripts\python -m pytest` |
| Core tests | `cd astrasync-core-lib; ..\traficom-integration\backend\.venv\Scripts\python -m pytest` |
| UI tests | `npm --prefix traficom-integration\ui test` |
| Process an IFIC issue | `python -m astrasync_data.ific_evaluate space\|terrestrial --issue … --m4 … --workbook … --out …` |
| Reproduce 3074 / 3076 | [`../04_Input_Output/REPRODUCIBILITY.md`](../04_Input_Output/REPRODUCIBILITY.md) |
