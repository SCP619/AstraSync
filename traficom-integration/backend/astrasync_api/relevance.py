"""Finland relevance, stage one of TR-REL-004: does a frequency range touch Finnish references?

Two kinds of Finnish reference, kept apart (TR-REL-001, TR-REL-005):
- M4 allocations, from the Traficom table of frequencies in Finland. An overlap says the band is
  allocated in Finland, not that anything is in use there.
- Special-interest stations, from the challenge workbook (synthetic). The workbook gives a centre
  frequency and a channel bandwidth; treating centre +/- half the channel as the occupied interval
  is an assumption, named in each match as its ``interval_basis``.

A match is a screening signal only. It never says interference, and service, geometry,
technical readiness and criterion stay unevaluated (null) here. Only records the caller may read
are screened, through the same rules as source search.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .authz import ObjectAccessPolicy
from .contract import CONTRACT_VERSION
from .contract.enums import ArtifactStatus, SourceType
from .contract.models import (
    FrequencyReferenceMatch,
    FrequencyRelevanceScreen,
    RelevanceGates,
    ScreenedReferenceSource,
)
from .identity import Principal
from .jobs import utc_now
from .library_tables import (
    ReferenceStationRow,
    SourceArtifactRow,
    SourceConnectorRow,
    SourceRecordLocationRow,
    SourceSearchRow,
)

RULE_VERSION = "frequency-screen/1.0.0"
RIGHT_READ = "READ"
MAX_MATCHES = 500
ALLOCATION_TYPES = (SourceType.M4_ALLOCATION.value,)
STATION_TYPES = (
    SourceType.CHALLENGE_SYNTHETIC_REFERENCE.value,
    SourceType.FINLAND_FREQUENCY_INTEREST.value,
)
_INDEXED = (ArtifactStatus.INDEXED.value, ArtifactStatus.INDEXED_WITH_WARNINGS.value)


@dataclass(frozen=True)
class ReferenceInterval:
    source_record_id: str
    source_id: str
    artifact_id: str
    kind: str
    field: str
    basis: str
    start_hz: float
    end_hz: float
    label: str | None
    is_synthetic: bool


def overlap(
    a_start: float, a_end: float, b_start: float, b_end: float
) -> tuple[float, float] | None:
    """Closed-interval overlap. Touching edges count, as a zero-width overlap."""
    start, end = max(a_start, b_start), min(a_end, b_end)
    return (start, end) if start <= end else None


def station_intervals(
    fields: dict[str, Any],
    *,
    record: str,
    source: str,
    artifact: str,
    label: str | None,
    synthetic: bool,
) -> list[ReferenceInterval]:
    """TX and RX intervals for one station: centre +/- half the channel, or the centre alone."""
    channel = fields.get("channel_bandwidth_hz")
    intervals = []
    for field, key in (("TX_FREQUENCY", "tx_frequency_hz"), ("RX_FREQUENCY", "rx_frequency_hz")):
        centre = fields.get(key)
        if not isinstance(centre, int | float) or centre <= 0:
            continue  # Unknown frequency: nothing to screen, and never a guess.
        if isinstance(channel, int | float) and channel > 0:
            basis, half = "CENTRE_PLUS_MINUS_HALF_CHANNEL_BANDWIDTH", channel / 2
        else:
            basis, half = "CENTRE_FREQUENCY_ONLY", 0.0
        intervals.append(
            ReferenceInterval(
                record,
                source,
                artifact,
                "SPECIAL_INTEREST_STATION",
                field,
                basis,
                max(centre - half, 0.0),
                centre + half,
                label,
                synthetic,
            )
        )
    return intervals


def screen(
    start_hz: float, end_hz: float, references: Iterable[ReferenceInterval]
) -> tuple[RelevanceGates, list[FrequencyReferenceMatch], bool]:
    """Pure screening. Returns gates, matches (sorted, capped) and whether the list was capped."""
    matches: list[FrequencyReferenceMatch] = []
    kinds: set[str] = set()
    bounds: list[tuple[float, float]] = []
    for ref in references:
        hit = overlap(start_hz, end_hz, ref.start_hz, ref.end_hz)
        if hit is None:
            continue
        kinds.add(ref.kind)
        bounds.append(hit)
        matches.append(
            FrequencyReferenceMatch(
                source_record_id=ref.source_record_id,
                source_id=ref.source_id,
                artifact_id=ref.artifact_id,
                reference_kind=ref.kind,
                reference_field=ref.field,
                interval_basis=ref.basis,
                reference_start_mhz=ref.start_hz / 1e6,
                reference_end_mhz=ref.end_hz / 1e6,
                overlap_start_mhz=hit[0] / 1e6,
                overlap_end_mhz=hit[1] / 1e6,
                label=ref.label,
                is_synthetic=ref.is_synthetic,
            )
        )
    matches.sort(
        key=lambda m: (m.reference_kind, m.overlap_start_mhz, m.source_record_id, m.reference_field)
    )
    reasons = []
    if "M4_ALLOCATION" in kinds:
        reasons.append("M4_ALLOCATION_OVERLAP")
    if "SPECIAL_INTEREST_STATION" in kinds:
        reasons.append("SPECIAL_INTEREST_STATION_OVERLAP")
    if not kinds:
        reasons.append("NO_FINNISH_REFERENCE_OVERLAP")
    reasons += ["SERVICE_NOT_EVALUATED", "GEOMETRY_NOT_EVALUATED"]
    gates = RelevanceGates(
        label="FREQUENCY_MATCH" if kinds else "NO_FREQUENCY_MATCH",
        reason_codes=reasons,
        rule_version=RULE_VERSION,
        overlap_start_mhz=min(b[0] for b in bounds) / 1e6 if bounds else None,
        overlap_end_mhz=max(b[1] for b in bounds) / 1e6 if bounds else None,
        frequency_match=bool(kinds),
        service_match=None,
        geometry_match=None,
        technical_data_ready=None,
        criterion_available=None,
    )
    return gates, matches[:MAX_MATCHES], len(matches) > MAX_MATCHES


def _latest_artifacts(
    session: Session, policy: ObjectAccessPolicy, principal: Principal, source_types: Sequence[str]
) -> list[tuple[SourceConnectorRow, SourceArtifactRow]]:
    """The newest indexed revision of each readable reference source in the caller's tenant."""
    connectors = session.scalars(
        select(SourceConnectorRow).where(
            SourceConnectorRow.tenant_id == principal.tenant_id,
            SourceConnectorRow.source_type.in_(source_types),
            policy.readable_clause(
                principal,
                RIGHT_READ,
                tenant_column=SourceConnectorRow.tenant_id,
                source_column=SourceConnectorRow.source_id,
                classification_column=SourceConnectorRow.usage_classification,
                synthetic_column=SourceConnectorRow.is_synthetic,
            ),
        )
    ).all()
    found = []
    for connector in connectors:
        newest = session.scalar(
            select(func.max(SourceArtifactRow.revision)).where(
                SourceArtifactRow.source_id == connector.source_id,
                SourceArtifactRow.status.in_(_INDEXED),
            )
        )
        if newest is None:
            continue
        artifact = session.scalars(
            select(SourceArtifactRow).where(
                SourceArtifactRow.source_id == connector.source_id,
                SourceArtifactRow.revision == newest,
                SourceArtifactRow.status.in_(_INDEXED),
            )
        ).first()
        if artifact is not None:
            found.append((connector, artifact))
    return found


def _readable(policy: ObjectAccessPolicy, principal: Principal) -> Any:
    return policy.readable_clause(
        principal,
        RIGHT_READ,
        tenant_column=SourceSearchRow.tenant_id,
        source_column=SourceSearchRow.source_id,
        classification_column=SourceSearchRow.classification,
        synthetic_column=SourceSearchRow.is_synthetic,
    )


def load_references(
    session: Session,
    policy: ObjectAccessPolicy,
    principal: Principal,
    start_mhz: float,
    end_mhz: float,
) -> tuple[list[ReferenceInterval], list[ScreenedReferenceSource]]:
    references: list[ReferenceInterval] = []
    screened: list[ScreenedReferenceSource] = []
    pairs = _latest_artifacts(session, policy, principal, ALLOCATION_TYPES + STATION_TYPES)
    for connector, artifact in pairs:
        screened.append(
            ScreenedReferenceSource(
                source_id=connector.source_id,
                source_type=connector.source_type,
                artifact_id=artifact.artifact_id,
                revision=artifact.revision,
                is_synthetic=artifact.is_synthetic,
            )
        )
        base = (
            select(SourceSearchRow, SourceRecordLocationRow)
            .join(
                SourceRecordLocationRow,
                SourceRecordLocationRow.source_record_id == SourceSearchRow.source_record_id,
            )
            .where(
                SourceSearchRow.artifact_id == artifact.artifact_id, _readable(policy, principal)
            )
        )
        if connector.source_type in ALLOCATION_TYPES:
            # Allocation intervals are exact in the index, so the overlap test runs in SQL.
            rows = session.execute(
                base.where(
                    SourceSearchRow.frequency_end_mhz >= start_mhz,
                    SourceSearchRow.frequency_start_mhz <= end_mhz,
                )
            ).all()
            for search, location in rows:
                lower = location.raw_fields.get("Sub_band_lower_limit__Hz_")
                upper = location.raw_fields.get("Sub_band_upper_limit__Hz_")
                start = float(lower) if lower else (search.frequency_start_mhz or 0.0) * 1e6
                end = float(upper) if upper else (search.frequency_end_mhz or 0.0) * 1e6
                references.append(
                    ReferenceInterval(
                        search.source_record_id,
                        search.source_id,
                        search.artifact_id,
                        "M4_ALLOCATION",
                        "SUB_BAND",
                        "PUBLISHED_SUB_BAND_LIMITS",
                        start,
                        end,
                        location.raw_fields.get("Services_in_Finland"),
                        search.is_synthetic,
                    )
                )
        else:
            # Station intervals depend on the channel bandwidth, so they are built per record.
            # This reads every station row of the artifact: fine for the workbook, not for tens of
            # millions of rows (Stage 6).
            station_rows = session.execute(
                select(SourceSearchRow, ReferenceStationRow.fields)
                .join(
                    ReferenceStationRow,
                    ReferenceStationRow.source_record_id == SourceSearchRow.source_record_id,
                )
                .where(
                    SourceSearchRow.artifact_id == artifact.artifact_id,
                    _readable(policy, principal),
                )
            ).all()
            for row in station_rows:
                station: SourceSearchRow = row[0]
                fields: dict[str, Any] = row[1]
                references.extend(
                    station_intervals(
                        fields,
                        record=station.source_record_id,
                        source=station.source_id,
                        artifact=station.artifact_id,
                        label=station.station_number,
                        synthetic=station.is_synthetic,
                    )
                )
    return references, screened


def screen_range(
    session: Session,
    policy: ObjectAccessPolicy,
    principal: Principal,
    start_mhz: float,
    end_mhz: float,
) -> FrequencyRelevanceScreen:
    references, screened = load_references(session, policy, principal, start_mhz, end_mhz)
    gates, matches, truncated = screen(start_mhz * 1e6, end_mhz * 1e6, references)
    if not screened:
        gates = gates.model_copy(
            update={
                "label": "NO_REFERENCE_DATA",
                "reason_codes": ["NO_FINNISH_REFERENCE_INDEXED"],
                "frequency_match": False,
            }
        )
    return FrequencyRelevanceScreen(
        schema_version=CONTRACT_VERSION,
        generated_at_utc=utc_now(),
        query_start_mhz=start_mhz,
        query_end_mhz=end_mhz,
        gates=gates,
        matches=matches,
        matches_truncated=truncated,
        sources_screened=screened,
        is_synthetic=any(m.is_synthetic for m in matches),
    )
