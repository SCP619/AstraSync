"""ITU BR IFIC acquisition: Space IFIC databases and Terrestrial BR IFIC MDB extracts.

Both are public downloads from www.itu.int, checked 2026-11-08:

- Space: https://www.itu.int/sns/wic/demowic.html lists years; each year page
  (``demowic<YY>.html``) has a table of publication date and Version 10 database
  ``../ific10/ific<NNNN>.zip``. The page states the service is "free ... on a trial basis until
  further notice" and that older years need the BR IFIC DVD from ITU sales. robots.txt does not
  disallow /sns/.
- Terrestrial: https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx links each
  issue's MDB extract ``/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific<NNNN>.zip``. The full BR
  IFIC (all data and software) is the ITU-sold DVD/ISO; only the extract is used here.

Discovery reads only these fixed pages on the one allowed host and parses links by strict
patterns, so a page can never point the worker elsewhere; downloads go through
``download_to_file`` (HTTPS, allow-listed host, no redirects, size limit). The issue range
(``ASTRASYNC_ITU_SPACE_ISSUES`` / ``ASTRASYNC_ITU_TERRESTRIAL_ISSUES``, ``"3073"`` or
``"3073-3076"``; default from 3070) bounds what is fetched, so a new installation does not
download every year.
An outage raises ``SourceUnavailable``, which never marks any publication as withdrawn.
"""

import os
import re
from datetime import UTC, datetime
from typing import BinaryIO

import httpx

from ..acquisition import (
    RemotePublication,
    SourceAccessDenied,
    SourceUnavailable,
    download_to_file,
)

HOST = "www.itu.int"
HEADERS = {"User-Agent": "AstraSync source monitor", "Accept-Encoding": "identity"}
SPACE_INDEX = "https://www.itu.int/sns/wic/demowic{yy:02d}.html"
SPACE_FILE = "https://www.itu.int/sns/ific10/ific{issue}.zip"
TERRESTRIAL_INDEX = "https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx"
TERRESTRIAL_FILE = "https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific{issue}.zip"
_SPACE_ROW = re.compile(
    r"<b>(\d{2})\.(\d{2})\.(\d{4})</b>.{0,400}?href=\"\.\./ific10/ific(\d{4})\.zip\"",
    re.DOTALL,
)
_TERRESTRIAL_LINK = re.compile(
    r"href=\"(?:https://www\.itu\.int)?/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific(\d{4})\.zip\""
)
MAX_INDEX_BYTES = 4 * 1024 * 1024


def _get_page(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url, follow_redirects=False)
    except httpx.HTTPError as exc:
        raise SourceUnavailable("ITU website unreachable") from exc
    if response.status_code in (401, 403):
        raise SourceAccessDenied
    if response.status_code != 200 or response.is_redirect:
        raise SourceUnavailable(f"HTTP {response.status_code}")
    if len(response.content) > MAX_INDEX_BYTES:
        raise SourceUnavailable("Index page larger than expected")
    return response.text


def parse_space_index(html: str) -> list[tuple[int, datetime]]:
    """(issue, publication date) pairs from one ``demowic<YY>.html`` page."""
    found = {}
    for day, month, year, issue in _SPACE_ROW.findall(html):
        found[int(issue)] = datetime(int(year), int(month), int(day), tzinfo=UTC)
    return sorted(found.items())


def parse_terrestrial_index(html: str) -> list[int]:
    return sorted({int(issue) for issue in _TERRESTRIAL_LINK.findall(html)})


def _head_size(client: httpx.Client, url: str) -> int | None:
    try:
        response = client.head(url, follow_redirects=False)
    except httpx.HTTPError:
        return None
    length = response.headers.get("Content-Length")
    return int(length) if response.status_code == 200 and length and length.isdigit() else None


def issue_range(value: str | None, default_first: int) -> tuple[int, int | None]:
    """``"3073"`` or ``"3073-3076"`` from server settings; anything else is refused."""
    if not value:
        return default_first, None
    match = re.fullmatch(r"(\d{4})(?:-(\d{4}))?", value.strip())
    if match is None:
        raise ValueError(f"Invalid IFIC issue range {value!r}")
    first, last = int(match.group(1)), int(match.group(2)) if match.group(2) else None
    if last is not None and last < first:
        raise ValueError(f"Invalid IFIC issue range {value!r}")
    return first, last


class _ItuClient:
    kind = ""
    file_url = ""
    range_setting = ""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        start_issue: int | None = None,
        last_issue: int | None = None,
        now: datetime | None = None,
    ) -> None:
        self._client = client or httpx.Client(headers=HEADERS, timeout=120.0)
        first, last = issue_range(os.environ.get(self.range_setting), 3070)
        self.start_issue = start_issue if start_issue is not None else first
        self.last_issue = last_issue if last_issue is not None else last
        self._now = now

    def _wanted(self, issue: int) -> bool:
        return issue >= self.start_issue and (self.last_issue is None or issue <= self.last_issue)

    def _url(self, issue: int) -> str:
        return self.file_url.format(issue=issue)

    def download(
        self, provider_issue_key: str, provider_version: str | None, destination: BinaryIO
    ) -> None:
        match = re.fullmatch(rf"{self.kind}-(\d{{4}})", provider_issue_key)
        if match is None:
            raise SourceUnavailable("Unknown publication")
        try:
            download_to_file(
                self._url(int(match.group(1))),
                destination,
                allowed_hosts={HOST},
                client=self._client,
                max_bytes=2 * 1024**3,
            )
        except httpx.HTTPError as exc:
            raise SourceUnavailable("ITU download interrupted") from exc


class ItuSpaceIficClient(_ItuClient):
    """``SourceClient`` for Space IFIC databases. Register for a ``SPACE_IFIC`` connector."""

    kind = "space-ific"
    file_url = SPACE_FILE
    range_setting = "ASTRASYNC_ITU_SPACE_ISSUES"

    def discover(self) -> list[RemotePublication]:
        year = (self._now or datetime.now(UTC)).year
        issues: dict[int, datetime] = {}
        for yy in sorted({(year - 1) % 100, year % 100}):
            for issue, published in parse_space_index(
                _get_page(self._client, SPACE_INDEX.format(yy=yy))
            ):
                issues[issue] = published
        if not issues:
            # A page that lists nothing is a changed or broken page, not an empty source.
            raise SourceUnavailable("No issue found on the Space IFIC index")
        return [
            RemotePublication(
                provider_issue_key=f"{self.kind}-{issue}",
                filename=f"ific{issue}.zip",
                provider_version="v10",
                published_at_utc=published,
                remote_size_bytes=_head_size(self._client, self._url(issue)),
            )
            for issue, published in sorted(issues.items())
            if self._wanted(issue)
        ]


class ItuTerrestrialIficClient(_ItuClient):
    """``SourceClient`` for Terrestrial BR IFIC MDB extracts. Register for ``TERRESTRIAL_IFIC``."""

    kind = "terrestrial-ific"
    file_url = TERRESTRIAL_FILE
    range_setting = "ASTRASYNC_ITU_TERRESTRIAL_ISSUES"

    def discover(self) -> list[RemotePublication]:
        issues = parse_terrestrial_index(_get_page(self._client, TERRESTRIAL_INDEX))
        if not issues:
            raise SourceUnavailable("No issue found on the Terrestrial BR IFIC page")
        return [
            RemotePublication(
                provider_issue_key=f"{self.kind}-{issue}",
                filename=f"brific{issue}.zip",
                provider_version="mdb-extract",
                published_at_utc=None,  # The page lists issues without dates; the MDB has it.
                remote_size_bytes=_head_size(self._client, self._url(issue)),
            )
            for issue in issues
            if self._wanted(issue)
        ]
