"""The Traficom open-data SourceClient against a mock transport. No network is used."""

import io
from datetime import UTC, datetime

import httpx
import pytest

from astrasync_api.acquisition import SourceAccessDenied, SourceUnavailable, UnsafeDownload
from astrasync_api.connectors import traficom_opendata as traficom
from astrasync_api.contract.interfaces import SourceClient

BODY = b'{"@odata.context":"x","value":[]}'


def client(handler: object) -> traficom.TraficomFrequencyTableClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return traficom.TraficomFrequencyTableClient(
        httpx.Client(transport=transport, headers=traficom.HEADERS)
    )


def ok(request: httpx.Request) -> httpx.Response:
    assert request.url == traficom.URL
    assert request.headers["Accept-Encoding"] == "identity"
    return httpx.Response(
        200,
        headers={
            "ETag": '"a91d8858-b835-411f-a09d-bbc3dde18138"',
            "Last-Modified": "Sat, 07 Nov 2026 11:38:04 GMT",
            "Content-Length": str(len(BODY)),
        },
        stream=httpx.ByteStream(BODY),
    )


def test_implements_the_source_client_protocol() -> None:
    assert isinstance(client(ok), SourceClient)


def test_discovery_reports_one_versioned_publication() -> None:
    [publication] = client(ok).discover()
    assert publication.provider_issue_key == traficom.ISSUE_KEY
    assert publication.provider_version == "a91d8858-b835-411f-a09d-bbc3dde18138"
    assert publication.published_at_utc == datetime(2026, 11, 7, 11, 38, 4, tzinfo=UTC)
    assert publication.remote_size_bytes == len(BODY)
    assert publication.publisher_signed is False  # No digest or signature is published.


def test_download_writes_the_exact_bytes() -> None:
    destination = io.BytesIO()
    client(ok).download(traficom.ISSUE_KEY, None, destination)
    assert destination.getvalue() == BODY


@pytest.mark.parametrize(
    ("status", "error"),
    [(403, SourceAccessDenied), (401, SourceAccessDenied), (503, SourceUnavailable)],
)
def test_refusals_and_outages_are_reported_as_such(status: int, error: type[Exception]) -> None:
    source = client(lambda request: httpx.Response(status))
    with pytest.raises(error):
        source.discover()
    with pytest.raises(error):
        source.download(traficom.ISSUE_KEY, None, io.BytesIO())


def test_network_failure_is_an_outage_not_a_retraction() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(SourceUnavailable):
        client(fail).discover()


def test_redirects_are_not_followed() -> None:
    redirect = client(
        lambda request: httpx.Response(302, headers={"Location": "https://example.test/x"})
    )
    with pytest.raises(UnsafeDownload):
        redirect.download(traficom.ISSUE_KEY, None, io.BytesIO())


def test_unknown_publication_is_refused() -> None:
    with pytest.raises(SourceUnavailable):
        client(ok).download("SOMETHING-ELSE", None, io.BytesIO())
