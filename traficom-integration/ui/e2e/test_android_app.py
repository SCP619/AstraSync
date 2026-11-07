"""A1 to A8 from DEVICE_TESTING.md, run against the debug APK on an emulator or phone.

Needs one device on adb with the app installed. The APK must be built with
`ASTRASYNC_E2E_WEBVIEW_DEBUG=true`, so ChromeDriver can attach to its WebView.
"""

import os
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from conftest import API, HERE, NATIVE_REDIRECT, App, api_token
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

PACKAGE = "fi.astrasync.app"
SDK = Path(os.environ.get("ANDROID_HOME", Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk"))
ADB = SDK / "platform-tools" / "adb.exe"
CHROMEDRIVER = Path(
    os.environ.get("ASTRASYNC_CHROMEDRIVER", HERE / ".drivers" / "chromedriver.exe")
)

Launch = Callable[[], App]


def adb(*args: str) -> str:
    return subprocess.run(
        [str(ADB), *args], capture_output=True, text=True, check=True, timeout=60
    ).stdout


def open_link(url: str) -> None:
    """Hands the sign-in result to Android, as the browser tab would."""
    # Quoted, because adb passes the command through the device's shell.
    adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", f"'{url}'", PACKAGE)


def resumed_package() -> str:
    """The package of the activity in front."""
    for line in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "topResumedActivity" in line or "mResumedActivity" in line:
            return line.split("/")[0].split()[-1]
    return ""


@pytest.fixture(scope="module")
def device(stack: None) -> Iterator[None]:
    assert ADB.exists(), f"adb missing: {ADB}"
    assert CHROMEDRIVER.exists(), f"ChromeDriver for the device's WebView missing: {CHROMEDRIVER}"
    assert PACKAGE in adb("shell", "pm", "list", "packages", PACKAGE), "Install the debug APK first"
    adb("reverse", "tcp:8800", "tcp:8800")
    adb("reverse", "tcp:8801", "tcp:8801")
    # Skip Chrome's first-run screens, so the sign-in tab loads straight away.
    adb("shell", "echo 'chrome --disable-fre --no-default-browser-check --no-first-run'"
        " > /data/local/tmp/chrome-command-line")
    adb("shell", "am", "force-stop", "com.android.chrome")
    os.environ["PATH"] = f"{ADB.parent}{os.pathsep}{os.environ['PATH']}"
    yield
    adb("shell", "am", "force-stop", PACKAGE)


@pytest.fixture
def launch(device: None) -> Iterator[Launch]:
    """Fully closes the app, then starts it fresh with ChromeDriver attached."""
    drivers: list[WebDriver] = []

    def start() -> App:
        adb("shell", "am", "force-stop", PACKAGE)
        options = webdriver.ChromeOptions()
        options.add_experimental_option("androidPackage", PACKAGE)
        options.add_experimental_option("androidActivity", ".MainActivity")
        for attempt in range(3):
            try:
                driver = webdriver.Chrome(options=options, service=Service(str(CHROMEDRIVER)))
                break
            except WebDriverException:
                # The app's process can take a moment to appear after a force-stop.
                if attempt == 2:
                    raise
                time.sleep(3)
        drivers.append(driver)
        app = App(driver, open_link=open_link)
        app.wait_for_text("Sign in")
        return app

    yield start
    for driver in drivers:
        try:
            driver.quit()
        except Exception:  # noqa: BLE001 - the app may already be closed.
            pass


def no_sideways_scroll(app: App) -> bool:
    return bool(
        app.driver.execute_script(
            "return document.documentElement.scrollWidth <= window.innerWidth + 1"
        )
    )


def test_a01_sign_in_opens_a_browser_tab(launch: Launch) -> None:
    app = launch()
    app.click("Continue to sign-in")
    app.wait(lambda _d: resumed_package() == "com.android.chrome", seconds=30)
    app.driver.back()  # Close the tab; the next tests sign in fully.


def test_a02_reviewer_sign_in_returns_and_closes_the_tab(launch: Launch) -> None:
    app = launch()
    request = app.sign_in("reviewer-a")
    assert request["code_challenge_method"] == "S256"
    assert request["redirect_uri"] == NATIVE_REDIRECT
    app.wait_for_text("Confirmed by the server for this session.")
    assert "Reviewer" in app.text()
    app.wait(lambda _d: resumed_package() == PACKAGE)


def test_a03_case_cards_fit_the_screen(launch: Launch) -> None:
    app = launch()
    app.sign_in("reviewer-a")
    app.wait_for_text("Your access")
    app.click("Cases", "a")
    app.wait_for_text("SYNTHETIC-DEMO-SPACE-001")
    assert no_sideways_scroll(app)


def test_a04_case_tabs_are_readable_and_keep_metrics_apart(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("Your access")
    app.click("Cases", "a")
    app.click_link("SYNTHETIC-DEMO-SPACE-003")
    app.click("Run analysis")
    app.wait_for_text("1 of 6", seconds=40)
    assert "+2.30 dB" in app.text()
    for tab in ("Overview", "Methods", "Criteria", "Evidence", "Draft and review"):
        app.click(tab)
        time.sleep(1)
        assert no_sideways_scroll(app), f"{tab} scrolls sideways"
    app.click("Methods")
    sections = app.driver.execute_script(
        "return [...document.querySelectorAll('section[aria-label]')].map(s => ["
        "s.getAttribute('aria-label'), s.querySelectorAll('table').length])"
    )
    assert sections, "No method tables shown"
    labels = [label for label, _ in sections]
    assert len(labels) == len(set(labels)), "A metric appears in more than one table"
    assert all(tables == 1 for _, tables in sections), sections
    # Each table is labelled with one metric, so PFD and EPFD can never share a table.
    assert set(labels) <= {
        "Power flux density (PFD)",
        "Equivalent PFD (EPFD)",
        "Field strength",
        "Basic transmission loss",
        "Received interference power",
        "No metric",
    }, labels


def test_a05_acknowledging_an_alert_is_recorded_on_the_server(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("Your access")
    app.click_link("Alerts")
    app.click_link("Potential exceedance")
    app.click("Acknowledge")
    app.wait_for_text("Acknowledged by")
    # What the Windows app would show: the server's record, read with a separate sign-in.
    alerts = httpx.get(
        f"{API}/api/v1/alerts",
        headers={"Authorization": f"Bearer {api_token('analyst-a')}"},
    ).json()["items"]
    exceedance = [a for a in alerts if a["safe_title"].startswith("Potential exceedance")]
    assert exceedance and all(a["status"] == "ACKNOWLEDGED" for a in exceedance), exceedance


def test_a06_returning_after_a_minute_still_works(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("DEMO-TENANT-A")
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(60)
    adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
    app.wait(lambda _d: resumed_package() == PACKAGE)
    app.wait(lambda _d: "DEMO-TENANT-A" in app.text() or "Continue to sign-in" in app.text())
    if "DEMO-TENANT-A" in app.text():
        app.click("Cases", "a")
        app.wait_for_text("SYNTHETIC-DEMO-SPACE-001")


def test_a07_reopening_requires_sign_in_with_no_earlier_data(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("DEMO-TENANT-A")
    reopened = launch()  # Force-stops the app, then starts it again.
    reopened.wait_for_text("Continue to sign-in")
    assert "DEMO-TENANT-A" not in reopened.text()


def test_a08_alerts_say_push_is_not_set_up_and_still_work(launch: Launch) -> None:
    app = launch()
    app.sign_in("reviewer-a")
    app.wait_for_text("Your access")
    app.click_link("Alerts")
    app.wait_for_text("Push notifications are not set up for this deployment")
    app.wait_for_text("Needs acknowledgment")
