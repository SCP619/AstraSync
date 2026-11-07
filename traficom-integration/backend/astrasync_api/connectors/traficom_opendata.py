"""Traficom open-data frequency allocation table (`Taajuusjakotaulukko`, API v13).

Public, no credentials. Licence: Creative Commons BY 4.0, as stated in the API's OpenAPI document
(https://opendata.traficom.fi/swagger/docs/v13), so displays and exports must attribute Traficom.
Checked 2026-11-07.

The endpoint returns the whole table as one JSON document and does not answer HEAD, so discovery
reads only the response headers of a GET and closes it. The ETag is the provider version. If the
server's cache issues a new ETag for unchanged content, the archive still keeps one artifact,
because identical bytes are de-duplicated on registration.
"""

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import BinaryIO

import httpx

from ..acquisition import (
    RemotePublication,
    SourceAccessDenied,
    SourceUnavailable,
    download_to_file,
)

URL = "https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko"
HOST = "opendata.traficom.fi"
ISSUE_KEY = "Taajuusjakotaulukko-v13"
FILENAME = "Taajuusjakotaulukko-v13.json"
HEADERS = {
    # Archive the document exactly as published, not a transfer-compressed copy.
    "Accept-Encoding": "identity",
    "Accept": "application/json",
    "User-Agent": "AstraSync source monitor",
}


def _published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


class TraficomFrequencyTableClient:
    """``SourceClient`` for the allocation table. Register as ``ASTRASYNC_SOURCE_CLIENTS``."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(headers=HEADERS, timeout=60.0)

    def discover(self) -> list[RemotePublication]:
        try:
            with self._client.stream("GET", URL, follow_redirects=False) as response:
                status = response.status_code
                headers = response.headers
        except httpx.HTTPError as exc:
            raise SourceUnavailable("Traficom open data unreachable") from exc
        if status in (401, 403):
            raise SourceAccessDenied
        if status != 200:
            raise SourceUnavailable(f"HTTP {status}")
        etag = headers.get("ETag")
        length = headers.get("Content-Length")
        return [
            RemotePublication(
                provider_issue_key=ISSUE_KEY,
                filename=FILENAME,
                provider_version=etag.strip('"') if etag else None,
                published_at_utc=_published_at(headers.get("Last-Modified")),
                remote_size_bytes=int(length) if length and length.isdigit() else None,
            )
        ]

    def download(
        self, provider_issue_key: str, provider_version: str | None, destination: BinaryIO
    ) -> None:
        if provider_issue_key != ISSUE_KEY:
            raise SourceUnavailable("Unknown publication")
        try:
            download_to_file(URL, destination, allowed_hosts={HOST}, client=self._client)
        except httpx.HTTPError as exc:
            raise SourceUnavailable("Traficom open data unreachable") from exc
