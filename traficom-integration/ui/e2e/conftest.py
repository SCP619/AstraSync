"""Automated device tests for the installed test apps (DEVICE_TESTING.md, W1 to W12, A1 to A8).

Drives the real packaged app through Microsoft Edge WebDriver in WebView2 mode, against a fresh
local test stack. The person's click on the sign-in page is replaced by a request to the local
test identity provider. The sign-in result still returns through the real `fi.astrasync.app://`
link that Windows hands to the app.
"""

import ctypes
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Callable, Iterator
from ctypes import wintypes
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
DRIVER = HERE / ".drivers" / "msedgedriver.exe"
APP = Path(
    os.environ.get(
        "ASTRASYNC_TEST_APP",
        Path(os.environ["LOCALAPPDATA"]) / "AstraSync Local Test" / "astrasync-desktop.exe",
    )
)
APP_PROCESS = APP.name
WINDOW_TITLE = "AstraSync (local test)"
IDP = "http://127.0.0.1:8801"
API = "http://127.0.0.1:8800"
NATIVE_REDIRECT = "fi.astrasync.app://auth/callback"

def _port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _kill_app() -> None:
    subprocess.run(["taskkill", "/F", "/IM", APP_PROCESS], capture_output=True, check=False)


@pytest.fixture(scope="session")
def stack() -> Iterator[None]:
    """A fresh local test stack with seeded made-up data, stopped at the end."""
    if _port_open(8800) or _port_open(8801):
        pytest.exit("Stop the running test stack first: ports 8800 or 8801 are in use.")
    shutil.rmtree(BACKEND / ".dev", ignore_errors=True)
    log = (HERE / ".stack.log").open("w")
    process = subprocess.Popen(
        [str(BACKEND / ".venv" / "Scripts" / "python.exe"), "tests/support/dev_stack.py", "all"],
        cwd=BACKEND,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(120):
            if _port_open(8800) and _port_open(8801):
                break
            time.sleep(0.5)
        else:
            pytest.exit("The test stack did not start. See e2e/.stack.log.")
        time.sleep(2)  # The worker starts just after the API.
        yield
    finally:
        _kill_app()
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, check=False
        )
        log.close()


class App:
    """One running copy of the installed app."""

    def __init__(self, driver: WebDriver, open_link: Callable[[str], None] = os.startfile) -> None:
        self.driver = driver
        self.open_link = open_link  # Hands a link to the operating system, as a browser would.

    def wait(self, condition: Callable[[WebDriver], Any], seconds: float = 20) -> Any:
        return WebDriverWait(self.driver, seconds, poll_frequency=0.25).until(condition)

    def text(self) -> str:
        return str(self.driver.execute_script("return document.body.innerText"))

    def wait_for_text(self, fragment: str, seconds: float = 20) -> None:
        try:
            self.wait(lambda _d: fragment in self.text(), seconds)
        except TimeoutException as exc:
            raise AssertionError(
                f"Expected {fragment!r}. The app shows:\n{self.text()[:1500]}"
            ) from exc

    def click(self, text: str, selector: str = "button") -> None:
        def find(_d: WebDriver) -> Any:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.text.strip() == text and element.is_enabled():
                    return element
            return False

        self.wait(find).click()

    def click_link(self, fragment: str) -> None:
        def find(_d: WebDriver) -> Any:
            for element in self.driver.find_elements(By.TAG_NAME, "a"):
                if fragment in element.text:
                    return element
            return False

        self.wait(find).click()

    def sign_in(self, persona: str) -> dict[str, str]:
        """Returns the sign-in request the app sent to the identity provider.

        The app opens it in the system browser. Tauri's call interface is read-only, so the test
        can't stop that browser tab opening; it answers the request directly instead.
        """
        before = httpx.get(f"{IDP}/dev/latest-sign-in-request").json().get("state")
        self.click("Continue to sign-in")

        def received(_d: WebDriver) -> Any:
            latest = httpx.get(f"{IDP}/dev/latest-sign-in-request").json()
            return latest if latest.get("state") not in (None, before) else False

        request: dict[str, str] = self.wait(received)
        approval = httpx.post(
            f"{IDP}/authorize",
            data={
                "subject": persona,
                "redirect_uri": request["redirect_uri"],
                "code_challenge": request["code_challenge"],
                "state": request["state"],
                "scope": request.get("scope", ""),
                "nonce": request.get("nonce", ""),
            },
            follow_redirects=False,
        )
        location = approval.headers["location"]
        assert location.startswith(f"{NATIVE_REDIRECT}?"), location
        self.open_link(location)
        return request


@pytest.fixture
def launch(stack: None) -> Iterator[Callable[[], App]]:
    """Starts the installed app. Every copy started is closed after the test."""
    assert APP.exists(), f"Install the local test package first: {APP} not found"
    assert DRIVER.exists(), f"WebView2 driver missing: {DRIVER}"
    drivers: list[WebDriver] = []

    def start() -> App:
        _kill_app()
        options = webdriver.EdgeOptions()
        options.use_webview = True
        options.binary_location = str(APP)
        driver = webdriver.Edge(options=options, service=Service(executable_path=str(DRIVER)))
        drivers.append(driver)
        app = App(driver)
        app.wait_for_text("Sign in")
        return app

    yield start
    for driver in drivers:
        try:
            driver.quit()
        except Exception:  # noqa: BLE001 - the app may already be closed.
            pass
    _kill_app()


def visible_app_windows() -> int:
    """Counts the app's visible top-level windows."""
    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd: int, _param: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buffer, 256)
            if buffer.value == WINDOW_TITLE:
                found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    return len(found)


def app_processes() -> int:
    listing = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {APP_PROCESS}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return sum(1 for line in listing.splitlines() if APP_PROCESS in line)


def api_token(persona: str) -> str:
    """A token for API set-up steps, from the same local identity provider."""
    import base64
    import hashlib
    import secrets

    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    approval = httpx.post(
        f"{IDP}/authorize",
        data={
            "subject": persona,
            "redirect_uri": NATIVE_REDIRECT,
            "code_challenge": challenge,
            "state": "setup",
            "scope": "openid astrasync.api",
        },
        follow_redirects=False,
    )
    code = parse_qs(urlsplit(approval.headers["location"]).query)["code"][0]
    token = httpx.post(
        f"{IDP}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": NATIVE_REDIRECT,
            "code_verifier": verifier,
            "client_id": "astrasync-dev-ui",
        },
    )
    return str(token.json()["access_token"])
