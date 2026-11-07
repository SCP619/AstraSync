# Device testing

This is how to close the Stage 7 exit test: install both apps, sign in, and run the alert and case flows on real devices. Everything uses **made-up data** on a local test stack, with no real account or identity provider.

**Limits of this test:** the stack proves the app's own flows. A real identity provider, real MFA, Android push and signed packages each still need their own test before release.

## 1. Get the test packages

On GitHub, open **Actions**, then **Native local test builds**, and use **Run workflow** on `main`. It also runs on pull requests that change the UI. Download these from the finished run:

- `astrasync-windows-LOCAL-TEST`: an unsigned installer, so Windows SmartScreen may warn about it.
- `astrasync-android-LOCAL-TEST`: a debug APK.

They only talk to `127.0.0.1`, so they can't reach anything else.

## 2. Start the local stack

From `traficom-integration/backend`, on the Windows PC:

```bash
.venv/Scripts/python tests/support/dev_stack.py all
```

Keep it running. To start again with fresh data, stop it and delete `traficom-integration/backend/.dev`.

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

## 5. Report results

Send the tables back with any failures. For a failure, these help most: the test number, a screenshot, and the output from the terminal running the stack.
