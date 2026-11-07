# AstraSync clients

One React and TypeScript UI, packaged for Windows (Tauri) and Android (Capacitor). The server stays authoritative: clients hold no RF logic, permissions or stored tokens.

**Status:** the web UI is tested. **The Windows and Android packages have not been built or installed yet,** so native sign-in, notifications and deep links are `DESIGNED`, not `TESTED`.

## Commands

```bash
npm ci
```

```bash
npm test
```

```bash
npm run contract:check
```

```bash
npm run build
```

## How the platforms differ

| | Web preview | Windows | Android |
| --- | --- | --- | --- |
| Sign-in | Redirect in the same tab | System browser, then a `fi.astrasync.app://` deep link | Same as Windows |
| New alerts | In-app | In-app, plus a local notification while the app runs | Push, and in-app when open |
| Access token | Memory only | Memory only | Memory only |

**Tokens:** nothing long-lived is stored, so there is no refresh token to protect. A restart signs in again, normally without a prompt because the system browser keeps the identity provider's session.

**Push payloads:** only the opaque alert ID, a generic category and a timestamp. A tapped notification opens `/alerts/{id}`, and the server re-authorizes that request.

## Windows

Needs [Rust](https://rustup.rs) and the Visual Studio C++ build tools. WebView2 is already on Windows 11.

```bash
npx tauri build
```

The installer is written to `src-tauri/target/release/bundle/nsis/`. Release builds also need a code-signing certificate.

## Android

Needs a JDK (21) and the Android SDK.

```bash
npx cap sync android
```

```bash
cd android && ./gradlew assembleDebug
```

### Turning on push

1. Create a Firebase project, or get approval for another push gateway.
2. Add its `google-services.json` to `android/app/`. **Don't commit it to a public repository.**
3. Build with `VITE_PUSH_CONFIGURED=true`.
4. On the server, set `ASTRASYNC_PUSH_TOKEN_KEY` and `ASTRASYNC_PUSH_GATEWAY`, and implement `PushGateway` for the provider.

Without these, the app doesn't register for push and says so on the Alerts screen. The inbox and in-app alerts keep working.

## Before a release

- Register `fi.astrasync.app://auth/callback` with the identity provider as a native redirect URI.
- Add these origins to the provider and to `ASTRASYNC_CORS_ORIGINS`: `http://tauri.localhost` (Windows) and `https://localhost` (Android).
- Sign the Windows installer and Android package.
- Run the sign-in, deep link, alert, acknowledgment and revocation flows on real devices.
- Consider verified Android App Links in place of the custom scheme. PKCE already protects the code from another app claiming the scheme.
