# Device testing

This is how to close the Stage 7 exit test: install both apps, sign in, and run the alert and case flows on real devices. Everything uses **made-up data** on a local test stack, with no real account or identity provider.

**Limits of this test:** the stack proves the app's own flows. A real identity provider, real MFA, Android push and signed packages each still need their own test before release.

## 1. Get the test packages

On GitHub, open **Actions**, then **Native local test builds**, and use **Run workflow** on `main`. It also runs on pull requests that change the UI. Download these from the finished run:

- `astrasync-windows-LOCAL-TEST`: an unsigned installer, so Windows SmartScreen may warn about it.
- `astrasync-android-LOCAL-TEST`: a debug APK.

They only talk to `127.0.0.1`, so they can't reach anything else.

## 2. Start the local stack

In PowerShell, from `traficom-integration\backend` on the Windows PC:

```powershell
.\.venv\Scripts\python.exe tests\support\dev_stack.py all
```

Wait for the line starting `Ready.`, and keep that window open for the whole test. **If the app says the identity provider can't be reached, check this first.**

To start again with fresh data, stop it with Ctrl+C, then run this and start it again:

```powershell
Remove-Item -Recurse -Force .dev
```

The sign-in page offers test personas and has no passwords. "Analyst, tenant A" and "Reviewer, tenant A" are the ones used most below.

## 3. Windows tests

Install the package on the same PC as the stack. Record **pass**, **fail** or **blocked**, and for a failure note what you saw.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| W1 | Open the app and choose **Continue to sign-in** | Your system browser opens, not a window inside the app | |
| W2 | Choose **Analyst, tenant A** | The browser hands back to the app, which shows the analyst's access and a `DEMO` label | |
| W3 | Open **Cases**, then `DEMO-SPACE-003`, and choose **Run analysis** | One method runs and the margin shows `+2.30 dB` | |
| W4 | Stay signed in for W3 | A Windows notification appears with only "Potential exceedance: expert review required" | |
| W5 | Open **Alerts**, open that alert, and choose **Acknowledge** | Status changes to Acknowledged | |
| W6 | Close the app fully, then reopen it | It asks you to sign in again, and no earlier data shows first | |
| W7 | Turn Windows notifications off for the app. Sign in as **Reviewer, tenant A**, open a case and record **Escalate as urgent** with a reason | No notification appears, and the critical alert still shows in **Alerts** | |
| W8 | Sign in as **Valid sign-in, no AstraSync account** | "No access to AstraSync", with a way to sign out | |
| W9 | Sign in as **Analyst with an expired token** | "Your session has ended" | |
| W10 | Sign in as **Analyst signed in without MFA** | A message that multi-factor sign-in is required | |
| W11 | Choose **Sign out** | Returns to sign-in, and the browser may ask to reopen the app | |
| W12 | While signed in, start a second copy of the app | The first window stays in use, with no second window | |

### Run W1 to W12 automatically

`e2e\` drives the installed app through Microsoft Edge WebDriver, and starts and stops a fresh stack itself, so stop any stack you started by hand first. The driver's major version must match WebView2 (see `edge://version`). Put `msedgedriver.exe` in `e2e\.drivers\`, which git ignores. In PowerShell, from `traficom-integration\ui\e2e`:

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe -m pytest test_windows_app.py -v -p no:cacheprovider
```

What it can't do:

- The person's click on the sign-in page is replaced by a direct request to the test identity provider. Each sign-in still opens a tab in your default browser, which you can close.
- W4, the Windows notification, can't be seen through WebDriver, so it stays a check by hand.
- W7 checks the critical alert, not that notifications stayed off.

## 4. Android tests

Needs a phone or emulator with USB debugging, and [Android platform tools](https://developer.android.com/tools/releases/platform-tools) on the PC. While connected, forward the two ports each time:

```bash
adb reverse tcp:8800 tcp:8800
```

```bash
adb reverse tcp:8801 tcp:8801
```

Then install the APK:

```bash
adb install app-debug.apk
```

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| A1 | Open the app and choose **Continue to sign-in** | A browser tab opens on the phone | |
| A2 | Choose **Reviewer, tenant A** | The tab closes and the app shows the reviewer's access | |
| A3 | Open **Cases** | Cards fit the screen with no sideways scrolling | |
| A4 | Open a case and read each tab | Units and values are readable, and PFD and EPFD stay in separate tables | |
| A5 | Open **Alerts**, and acknowledge one | Status changes to Acknowledged, and the Windows app shows the same when signed in | |
| A6 | Switch away for a minute, then return | The app still works, or asks you to sign in | |
| A7 | Fully close the app, then reopen it | It asks you to sign in again, with no earlier data | |
| A8 | Read the Alerts screen | It says push isn't set up, and the inbox still works | |

**Android push can't pass here.** It needs a Firebase project or another approved gateway.

### Run A1 to A8 automatically

This needs a debug APK that allows WebView debugging, which the CI package doesn't. Build it from `traficom-integration\ui` with JDK 21 and the Android SDK, setting the same `VITE_*` values as `.github/workflows/native-local-test.yml`:

```powershell
npm run build; $env:ASTRASYNC_E2E_WEBVIEW_DEBUG = "true"; npx cap copy android; cd android; .\gradlew.bat assembleDebug
```

Install it on one emulator or phone. The emulator needs Windows Hypervisor Platform turned on. Put a ChromeDriver whose major version matches the device's Android System WebView in `e2e\.drivers\chromedriver.exe`, from [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/). The test forwards the ports itself. From `traficom-integration\ui\e2e`:

```powershell
.\.venv\Scripts\python.exe -m pytest test_android_app.py -v -p no:cacheprovider
```

What it can't do:

- As on Windows, the person's click on the sign-in page is replaced by a request to the test identity provider. The sign-in result reaches the app through Android's `fi.astrasync.app://` link handling.
- A5 checks the acknowledgment on the server, which is what the Windows app reads, instead of looking at the Windows app.
- A3 and A4 check for sideways scrolling and separate metric tables, not how readable the text looks to a person.

## Results, 2026-11-07

Made-up data on the local stack. Windows 11 with the CI test package; Android 15 emulator (Pixel 6, WebView 124) with a local debug build.

| Tests | Result |
| --- | --- |
| W1 to W7 | Pass by hand |
| W1 to W3, W5, W6, W8 to W12 | Pass, automated |
| W4 notification | Pass by hand only |
| W7 | Found a bug: "Decision recorded." disappeared after the lists reloaded. Fixed, and confirmed in the web build; the installed package predates the fix |
| A1 to A8 | Pass, automated, twice in a row |
| Android push | Not tested: no gateway |

## 5. Report results

Send the tables back with any failures. For a failure, these help most: the test number, a screenshot, and the output from the terminal running the stack.
