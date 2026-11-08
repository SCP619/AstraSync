# Installation (Windows, PowerShell)

The full, maintained guide is `docs/WINDOWS_DEVELOPMENT_SETUP.md` in the repository (tools,
ports, data, native builds, smoke test). Minimum for evaluators:

| Tool | Version (as in CI) |
| --- | --- |
| Git | current |
| Python | 3.11 |
| Node.js / npm | Node 22 |
| Optional | PostgreSQL 16+ (tests only), Rust + VS C++ build tools (Windows package), JDK 21 + Android SDK 35 (Android), n8n + Ollama `qwen3:8b` (local AI) |

```powershell
git clone https://github.com/SCP619/AstraSync.git; Set-Location AstraSync
```

```powershell
py -3.11 -m venv traficom-integration\backend\.venv
```

```powershell
traficom-integration\backend\.venv\Scripts\python -m pip install -r traficom-integration\backend\requirements-dev.lock -r astrasync-core-lib\requirements.lock
```

```powershell
traficom-integration\backend\.venv\Scripts\python -m pip install --no-deps -e traficom-integration\backend -e astrasync-core-lib
```

```powershell
npm --prefix traficom-integration\ui ci
```

Ports default to API 8800, identity provider 8801, UI 5173 on 127.0.0.1. If Windows reserves them
(`netsh interface ipv4 show excludedportrange protocol=tcp`), set `ASTRASYNC_DEV_API_PORT` and
`ASTRASYNC_DEV_IDP_PORT` in `traficom-integration\backend\dev_stack.local.env` and the matching
`VITE_API_BASE_URL` / `VITE_OIDC_AUTHORITY` in `traficom-integration\ui\.env.development.local`
(both git-ignored; templates in the repository).

Start the stack and UI: [`../01_Demo/DEMO_ACCESS.md`](../01_Demo/DEMO_ACCESS.md).
