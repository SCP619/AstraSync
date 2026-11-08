# Windows development setup

PowerShell instructions for a new Windows PC. No step needs a particular user name or folder; run
everything from the clone. Versions come from CI (`.github/workflows/`) and the lock files.

## 1. Tools

| Tool | Version | Needed for |
| --- | --- | --- |
| Git for Windows | current | Everything |
| Python | 3.11 (CI uses 3.11; `requires-python >= 3.11`) | Backend, core library, dev stack |
| Node.js + npm | Node 22 (CI); npm comes with it | UI, contract generation, Tauri and Capacitor CLIs |
| Claude Code | current | Development sessions |
| PostgreSQL | 16 or later, optional | Only to run the backend tests against PostgreSQL |
| Rust (rustup) + Visual Studio C++ build tools | stable | Windows (Tauri) builds only; WebView2 ships with Windows 11 |
| JDK | 21 (Temurin in CI) | Android builds only |
| Android SDK | compile/target SDK 35, min SDK 23 (`ui/android/variables.gradle`) | Android builds only |

Install Claude Code with `npm install -g @anthropic-ai/claude-code`, or use the Claude desktop
app's Code tab. Check: `git --version`, `py -3.11 --version`, `node --version`,
`npm --version`, `claude --version`.

## 2. GitHub access as SCP619

The remote uses the SSH alias `github-scp619`. Never copy a private key into the repository or
any document.

Use a new key for the new PC (recommended), or move the existing key with a secure method you
control (encrypted USB, password manager), never by e-mail or chat.

```powershell
ssh-keygen -t ed25519 -C "priyoshaktiman@gmail.com" -f "$HOME\.ssh\id_ed25519_scp619"
```

Add the `.pub` file's contents to the SCP619 GitHub account (Settings → SSH and GPG keys). Then
add to `$HOME\.ssh\config`:

```
Host github-scp619
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_scp619
    IdentitiesOnly yes
```

```powershell
ssh -T git@github-scp619
```

Expect "Hi SCP619! You've successfully authenticated". Any other account name means the wrong
key: stop and fix it before pushing.

## 3. Clone and identity

```powershell
git clone git@github-scp619:SCP619/AstraSync.git
```

```powershell
Set-Location AstraSync
```

```powershell
git config user.name "SCP619"
```

```powershell
git config user.email "priyoshaktiman@gmail.com"
```

```powershell
git log --oneline -3
```

`AstraSync-scp619/` may exist in old local copies: it is an obsolete backup, not in Git. Ignore it.

Turn off Claude attribution for this repository by creating `.claude\settings.local.json`
(git-ignored):

```json
{ "attribution": { "commit": "", "pr": "", "sessionUrl": false } }
```

## 4. Python environment

One virtual environment in `traficom-integration\backend\.venv` serves the backend, the core
library and the dev stack (as in CI).

```powershell
py -3.11 -m venv traficom-integration\backend\.venv
```

```powershell
traficom-integration\backend\.venv\Scripts\python -m pip install -r traficom-integration\backend\requirements-dev.lock -r astrasync-core-lib\requirements.lock
```

```powershell
traficom-integration\backend\.venv\Scripts\python -m pip install --no-deps -e traficom-integration\backend -e astrasync-core-lib
```

## 5. UI dependencies

```powershell
npm --prefix traficom-integration\ui ci
```

## 6. Local settings and ports

Defaults: API 8800, development identity provider 8801, UI 5173, all on 127.0.0.1. Check first
whether Windows reserves them (socket error 10048):

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

```powershell
Get-NetTCPConnection -LocalPort 8800,8801,5173 -ErrorAction SilentlyContinue
```

If a port is reserved or in use, pick free ones and create the two git-ignored files (the old PC
used 18800 and 18801; choose what is free on this one).

`traficom-integration\backend\dev_stack.local.env` (template:
`dev_stack.local.env.example`):

```
ASTRASYNC_DEV_API_PORT=18800
ASTRASYNC_DEV_IDP_PORT=18801
```

`traficom-integration\ui\.env.development.local`, with the same ports:

```
VITE_API_BASE_URL=http://127.0.0.1:18800
VITE_OIDC_AUTHORITY=http://127.0.0.1:18801
VITE_OIDC_CLIENT_ID=astrasync-dev-ui
VITE_OIDC_SCOPE=openid astrasync.api
```

Issuer, discovery, JWKS, CORS and redirect URIs all derive from these values
(`tests/support/dev_ports.py`). The stack checks ports before starting and refuses invalid,
duplicate or unbindable ones. Environment variables of the same names override the file. To use the
real public sources, add `ASTRASYNC_DEV_REAL_SOURCES=1` to `dev_stack.local.env` (section 9).

## 7. Run the development stack

The dev stack runs the identity provider, the API and the worker against SQLite in
`traficom-integration\backend\.dev\` (created on first start, git-ignored; delete it to start
fresh), applies migrations and seeds demo personas and synthetic
data. From the repository root:

```powershell
traficom-integration\backend\.venv\Scripts\python traficom-integration\backend\tests\support\dev_stack.py all
```

Parts can also run separately: `... dev_stack.py idp`, `... api`, `... worker`. In a second
terminal:

```powershell
npm --prefix traficom-integration\ui run dev
```

Open http://127.0.0.1:5173 and choose a persona (no passwords). Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8800/healthz -UseBasicParsing
```

(use your API port).

## 8. Tests and builds

```powershell
Set-Location traficom-integration\backend
```

```powershell
.venv\Scripts\python -m ruff check .
```

```powershell
.venv\Scripts\python -m mypy
```

```powershell
.venv\Scripts\python -m astrasync_api.contract.export --check
```

```powershell
.venv\Scripts\python -m pytest
```

PostgreSQL (optional; the database must be disposable, its `public` schema is dropped):

```powershell
$env:ASTRASYNC_TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/astrasync_test"
```

```powershell
.venv\Scripts\python -m pytest
```

Core library (from `astrasync-core-lib`):

```powershell
..\traficom-integration\backend\.venv\Scripts\python -m pytest
```

UI (from `traficom-integration\ui`):

```powershell
npm run contract:check
```

```powershell
npm test
```

```powershell
npm run build
```

Windows package (Rust and C++ build tools needed), from `traficom-integration\ui`:

```powershell
npx tauri build
```

Android debug APK (JDK 21, Android SDK), from `traficom-integration\ui`:

```powershell
npm run build
```

```powershell
npx cap sync android
```

```powershell
Set-Location android; .\gradlew.bat assembleDebug
```

CI builds both packages on every PR, so local native builds are only needed for device testing
(`traficom-integration\ui\DEVICE_TESTING.md`).

## 9. Data that Git does not carry

These files are needed only for real-data tests, evaluation runs, and loading real sources into the
dev stack. Everything else works without them. Keep them **outside** the clone (for example a
sibling folder `AstraSync_data\`), never in Git.

| File | Purpose | Public? | How to get it | SHA-256 (used here) |
| --- | --- | --- | --- | --- |
| `ific3074.zip`, `ific3073.zip` | Space IFIC (SNS v10 `.mdb`) | Public, ITU "free on a trial basis" | `https://www.itu.int/sns/ific10/ific3074.zip` (and 3073), or the dev stack's ITU-SPACE-IFIC source check | `c8adf75044bca9d6a2be4213d051805f1b0a88d716fb184bcb1cd812216da721`, `e1bd33e94e4342e6723a898630adac718c8b6406df594cef19a92b4a8b983513` |
| `brific3076.zip`, `brific3075.zip` | Terrestrial BR IFIC MDB extract | Public | `https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3076.zip` (and 3075), or the ITU-TERRESTRIAL-IFIC source check | `ba9d0605a4a5494162e17650c290401d84deaef29030cbdbb61e4b00c834c4c2`, `6f63a3dee548422cc722fd95adf7ce99f13abd8c786459d535c73e3320ed92f7` |
| `ReadMe_3076.pdf` | ITU per-part counts for reconciliation | Public | `https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/ReadMe/ReadMe_3076.pdf` | `4e7e5c1100fcafdf4087ae5c1e427916f7fca0e5f77115f683bfbf77437d1739` |
| `Taajuusjakotaulukko-v13.json` | Finnish M4 table | Public, CC BY 4.0 | `https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko` or the TRAFICOM-M4 source check. Content changes over time (ETag) | `41ffdd0ed84a40c19fd4bb3771699a63c879b1ad4f2201dcb1cd3c37524871fb` (snapshot of 2026-11-08) |
| `Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx` | Special-interest stations (synthetic) | Challenge data, not public; kept out of Git | Challenge platform, or copy from the old PC by a private means | `bb7f481f085fb6c457efc04b9b6bb8250c42ea81bab4b4a0e518c93834e03c8a` |
| P.1546 reference (`p1546-main/matlab`) | Validation of the P.1546 port | Public (ITU-R WP 3K reference, permissive licence) | `https://github.com/eeveetza/p1546` (download as zip) | — |

Check a file:

```powershell
Get-FileHash .\ific3074.zip -Algorithm SHA256
```

Real-data tests read these variables (unset: the tests are skipped and say so):

```powershell
$env:ASTRASYNC_IFIC_DATA = "<folder with the zips>"
```

```powershell
$env:ASTRASYNC_P1546_REFERENCE = "<...>\p1546-main\matlab"
```

```powershell
$env:ASTRASYNC_TRAFICOM_WORKBOOK = "<...>\Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx"
```

Regenerate the evaluation outputs (already committed under `evaluation/`): see
`evaluation\README.md`. Without the workbook, special-interest overlaps are empty and priorities
differ, so use the same workbook to reproduce the committed results.

Real sources in the dev stack: with `ASTRASYNC_DEV_REAL_SOURCES=1`, sign in as the Administrator
persona and check `TRAFICOM-M4`, then the ITU sources; upload the workbook to `CHALLENGE-WORKBOOK`
as the Analyst. Space 3074 needs about 3 minutes to parse and the parser memory limit the dev stack
sets (6 GB).

## 10. Smoke test for a new PC

1. `ssh -T git@github-scp619` greets SCP619.
2. `git status` is clean on `main`; `git log -1` matches GitHub.
3. Backend: `ruff`, `mypy` and `contract.export --check` pass; `pytest` passes (about 3–4 minutes).
4. UI: `npm run contract:check` and `npm test` pass.
5. The dev stack starts, `/healthz` returns 200, and a persona signs in at http://127.0.0.1:5173.
