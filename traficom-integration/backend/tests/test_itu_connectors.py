"""ITU BR IFIC connectors: strict index parsing, issue ranges, transfer policy, outages."""

import io
from datetime import UTC, datetime

import httpx
import pytest

from astrasync_api.acquisition import SourceAccessDenied, SourceUnavailable, UnsafeDownload
from astrasync_api.connectors import itu_brific as itu

# Shapes copied from the live pages (2026-11-08), reduced to two issues.
SPACE_PAGE = """
<tr> <td align="center"><b>23.06.2026</b></td> <td align="center"><b>
<a href="../ific10/ific3074.zip">3074</a></b></td> <td align="center">
<a href="//www.itu.int/net/ITU-R/space/snl/bresult/radvance.asp?sel_ific=3074&amp;ie=y">View</a>
</td> </tr>
<tr> <td align="center"><b>09.06.2026</b></td> <td align="center"><b>
<a href="../ific10/ific3073.zip">3073</a></b></td></tr>
<a href="https://evil.example/ific10/ific9999.zip">not an ITU link</a>
"""
TERRESTRIAL_PAGE = """
<a href="/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3076.zip">IFIC3076</a>
<a href="/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3075.zip">IFIC3075</a>
<a href="https://evil.example/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3999.zip">x</a>
"""


def _client(routes: dict[str, httpx.Response]) -> httpx.Client:
    # Snapshots, so each request gets a fresh response (one URL may get a HEAD, then a GET).
    snapshots = {url: (r.status_code, dict(r.headers), r.read()) for url, r in routes.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        found = snapshots.get(str(request.url))
        if found is None:
            return httpx.Response(404)
        status, headers, content = found
        return httpx.Response(status, headers=headers, stream=httpx.ByteStream(content))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_index_parsers_accept_only_itu_links() -> None:
    assert itu.parse_space_index(SPACE_PAGE) == [
        (3073, datetime(2026, 6, 9, tzinfo=UTC)),
        (3074, datetime(2026, 6, 23, tzinfo=UTC)),
    ]
    assert itu.parse_terrestrial_index(TERRESTRIAL_PAGE) == [3075, 3076]


def test_space_discovery_reads_current_and_previous_year_within_the_range() -> None:
    routes = {
        itu.SPACE_INDEX.format(yy=26): httpx.Response(200, text=SPACE_PAGE),
        itu.SPACE_INDEX.format(yy=25): httpx.Response(200, text=""),
        itu.SPACE_FILE.format(issue=3074): httpx.Response(200, headers={"Content-Length": "60"}),
    }
    client = itu.ItuSpaceIficClient(
        _client(routes), start_issue=3074, now=datetime(2026, 11, 8, tzinfo=UTC)
    )
    [publication] = client.discover()
    assert publication.provider_issue_key == "space-ific-3074"
    assert publication.filename == "ific3074.zip"
    assert publication.published_at_utc == datetime(2026, 6, 23, tzinfo=UTC)
    assert publication.remote_size_bytes == 60


def test_terrestrial_discovery_and_download() -> None:
    body = b"PK\x03\x04 not a real archive"
    routes = {
        itu.TERRESTRIAL_INDEX: httpx.Response(200, text=TERRESTRIAL_PAGE),
        itu.TERRESTRIAL_FILE.format(issue=3076): httpx.Response(
            200, content=body, headers={"Content-Length": str(len(body))}
        ),
    }
    client = itu.ItuTerrestrialIficClient(_client(routes), start_issue=3076)
    assert [p.provider_issue_key for p in client.discover()] == ["terrestrial-ific-3076"]
    sink = io.BytesIO()
    client.download("terrestrial-ific-3076", "mdb-extract", sink)
    assert sink.getvalue() == body
    with pytest.raises(SourceUnavailable):
        client.download("../../etc/passwd", None, io.BytesIO())


def test_issue_ranges_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    assert itu.issue_range("3073-3074", 3070) == (3073, 3074)
    assert itu.issue_range(None, 3070) == (3070, None)
    for bad in ("30", "3074-3073", "3073;rm"):
        with pytest.raises(ValueError):
            itu.issue_range(bad, 3070)
    monkeypatch.setenv("ASTRASYNC_ITU_TERRESTRIAL_ISSUES", "3075-3075")
    routes = {itu.TERRESTRIAL_INDEX: httpx.Response(200, text=TERRESTRIAL_PAGE)}
    client = itu.ItuTerrestrialIficClient(_client(routes))
    assert [p.provider_issue_key for p in client.discover()] == ["terrestrial-ific-3075"]


def test_outages_redirects_and_refusals_are_reported_never_as_withdrawals() -> None:
    empty = itu.ItuTerrestrialIficClient(
        _client({itu.TERRESTRIAL_INDEX: httpx.Response(200, text="<html></html>")})
    )
    with pytest.raises(SourceUnavailable):
        empty.discover()  # A page that lists nothing is broken, not an empty source.
    down = itu.ItuTerrestrialIficClient(_client({itu.TERRESTRIAL_INDEX: httpx.Response(503)}))
    with pytest.raises(SourceUnavailable):
        down.discover()
    denied = itu.ItuTerrestrialIficClient(_client({itu.TERRESTRIAL_INDEX: httpx.Response(403)}))
    with pytest.raises(SourceAccessDenied):
        denied.discover()
    redirect = itu.ItuTerrestrialIficClient(
        _client(
            {
                itu.TERRESTRIAL_FILE.format(issue=3076): httpx.Response(
                    302, headers={"Location": "http://169.254.169.254/"}
                )
            }
        )
    )
    with pytest.raises(UnsafeDownload):
        redirect.download("terrestrial-ific-3076", None, io.BytesIO())
