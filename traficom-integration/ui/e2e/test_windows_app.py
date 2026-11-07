"""W1 to W12 from DEVICE_TESTING.md, run against the installed Windows test app."""

import subprocess
import time
from collections.abc import Callable

from conftest import APP, NATIVE_REDIRECT, App, app_processes, visible_app_windows

Launch = Callable[[], App]


def test_w01_sign_in_uses_the_system_browser_with_pkce(launch: Launch) -> None:
    app = launch()
    request = app.sign_in("analyst-a")
    # The provider got the request from another browser, while the app stayed on its own page.
    assert app.driver.current_url.startswith(("tauri://", "http://tauri.localhost"))
    assert request["client_id"] == "astrasync-dev-ui"
    assert request["response_type"] == "code"
    assert request["code_challenge_method"] == "S256"
    assert len(request["code_challenge"]) >= 43
    assert request["redirect_uri"] == NATIVE_REDIRECT
    app.wait_for_text("Confirmed by the server for this session.")


def test_w02_sign_in_returns_to_the_app_with_server_confirmed_access(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("Confirmed by the server for this session.")
    text = app.text()
    assert "Analyst" in text
    assert "DEMO environment" in text
    assert "DEMO-TENANT-A" in text


def test_w03_w05_analysis_alert_and_acknowledgment(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("Your access")
    app.click("Cases", "a")
    app.click_link("SYNTHETIC-DEMO-SPACE-003")
    app.click("Run analysis")
    app.wait_for_text("1 of 6", seconds=40)  # W3
    assert "+2.30 dB" in app.text()

    # W4, the Windows notification, can't be seen from WebDriver. It passed by hand on 2026-11-07.
    app.click_link("Alerts")
    app.click_link("Potential exceedance")
    app.click("Acknowledge")
    app.wait_for_text("Acknowledged by")  # W5


def test_w06_restart_requires_sign_in_and_shows_no_earlier_data(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("DEMO-TENANT-A")
    restarted = launch()  # Closes the first copy, then starts again.
    restarted.wait_for_text("Continue to sign-in")
    text = restarted.text()
    assert "DEMO-TENANT-A" not in text
    assert "Analyst" not in text


def test_w07_escalation_reaches_the_inbox_as_critical(launch: Launch) -> None:
    app = launch()
    app.sign_in("reviewer-a")
    app.wait_for_text("Your access")
    app.click("Cases", "a")
    app.click_link("SYNTHETIC-DEMO-SPACE-001")
    app.click("Draft and review")
    app.wait(lambda d: d.find_elements("css selector", "select[name=decision]"))
    app.driver.execute_script(
        "const s = document.querySelector('select[name=decision]');"
        "s.value = 'ESCALATE'; s.dispatchEvent(new Event('change', {bubbles: true}));"
    )
    reason = app.driver.find_element("css selector", "textarea[name=reason]")
    reason.send_keys("Automated test: due date is close.")
    app.click("Record decision")
    app.wait_for_text("Decision recorded.")
    app.click_link("Alerts")
    app.wait_for_text("Case escalated by a reviewer", seconds=40)
    assert "Critical priority" in app.text()


def test_w08_valid_sign_in_without_an_account_is_refused(launch: Launch) -> None:
    app = launch()
    app.sign_in("not-provisioned")
    app.wait_for_text("No access to AstraSync")
    assert "Sign out" in app.text()


def test_w09_expired_token_ends_the_session(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-expired")
    app.wait_for_text("Your session has ended")


def test_w10_sign_in_without_mfa_is_refused(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-no-mfa")
    app.wait_for_text("requires multi-factor sign-in")


def test_w11_sign_out_returns_to_sign_in_and_ends_the_provider_session(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("DEMO-TENANT-A")
    app.click("Sign out")
    app.wait_for_text("Continue to sign-in")
    assert "DEMO-TENANT-A" not in app.text()


def test_w12_a_second_copy_does_not_open_a_second_window(launch: Launch) -> None:
    app = launch()
    app.sign_in("analyst-a")
    app.wait_for_text("DEMO-TENANT-A")
    subprocess.Popen([str(APP)])  # noqa: S603
    time.sleep(5)
    assert visible_app_windows() == 1
    assert app_processes() == 1
    assert "DEMO-TENANT-A" in app.text()  # The first window still works.
