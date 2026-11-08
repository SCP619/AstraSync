"""Parsers for ITU BR IFIC databases (Microsoft Access ``.mdb``, delivered zipped).

Sources (public, checked 2026-11-08):
- Space: "Space Circular Online", https://www.itu.int/sns/wic/demowic.html, one Version 10 SNS
  database per issue (``ific<NNNN>.zip``), "a free service on a trial basis until further
  notice". Field meanings: ITU "SNS data items" v9.1
  (https://www.itu.int/en/ITU-R/space/Documents/sns_dbv91.pdf); no v10 dictionary is published,
  so a field whose v10 meaning could differ is kept raw and flagged, never reinterpreted.
- Terrestrial: BR IFIC (Terrestrial Services) MDB extract, ``brific<NNNN>.zip``, linked from
  https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx. Field meanings: the BR IFIC
  Preface (PREFACE_EN.pdf, "data dictionary" tables, sections 1-9).

Rules:
- The archive must hold exactly one ``.mdb`` member with a safe name, within size and ratio
  limits; anything else is refused (quarantine), never partly read.
- Raw values are kept as text in ``raw_fields``. Normalised values carry the unit in the field
  name. Missing stays missing: no zero, no default, no guessed unit.
- The issue number comes from the database itself (``pub_current_circ`` for terrestrial, the
  notices' ``wic_no`` for space) and must match the file name; a mismatch is refused.
- Terrestrial notices are the rows published in this issue (``stage = NOTICE``). ``RECORDED``
  rows are the existing assignments that a MODIFY or SUPPRESS notice targets; they are kept as
  context records, so a modification can be compared field by field, and are never screened as
  new activity.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

SPACE_SOURCE_TYPE = "SPACE_IFIC"
TERRESTRIAL_SOURCE_TYPE = "TERRESTRIAL_IFIC"
SPACE_PARSER_VERSION = "itu-space-ific-sns-v10/1.0.0"
TERRESTRIAL_PARSER_VERSION = "itu-terrestrial-ific-mdb/1.0.0"
SPACE_SCHEMA_VERSION = "itu-sns/v10"
TERRESTRIAL_SCHEMA_VERSION = "itu-brific-terrestrial/mdb"

MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_DATABASE_BYTES = 4 * 1024**3
MAX_COMPRESSION_RATIO = 200
_SPACE_NAME = re.compile(r"^ific(\d{4})\.(zip|mdb)$", re.IGNORECASE)
_TERRESTRIAL_NAME = re.compile(r"^brific(\d{4})\.(zip|mdb)$", re.IGNORECASE)

# Preface section 8.6 (pwr_eiv) and 9.3 (gain_type).
POWER_TYPES = {"I": "EIRP", "E": "ERP", "V": "EMRP"}
GAIN_TYPES = {"I": "ISOTROPIC", "D": "HALF_WAVE_DIPOLE", "V": "SHORT_VERTICAL"}
# Preface station classes for the land mobile service (Appendix: classes of station).
LAND_MOBILE_CLASSES = frozenset({"FB", "ML", "FL"})
# SNS notice table, ntc_type.
NOTICE_TYPES = {
    "G": "GSO_SPACE_STATION",
    "N": "NON_GSO_SPACE_STATION",
    "S": "SPECIFIC_EARTH_STATION",
    "T": "TYPICAL_EARTH_STATION",
    "R": "RADIO_ASTRONOMY_STATION",
}


class IficFormatError(ValueError):
    """The file is not the expected IFIC database. Quarantined, never partly read."""


def issue_from_name(name: str, kind: str) -> int | None:
    """The issue in an ITU file name (``ific3074.zip``, ``brific3076.mdb``), or None."""
    pattern = _SPACE_NAME if kind == SPACE_SOURCE_TYPE else _TERRESTRIAL_NAME
    match = pattern.match(PurePosixPath(name).name)
    return int(match.group(1)) if match else None


@contextmanager
def open_database(artifact: Path, kind: str, original_name: str | None = None) -> Iterator[Path]:
    """Yields the ``.mdb`` path, extracting it from a zip with bounded size first."""
    name = original_name or artifact.name
    if artifact.stat().st_size > MAX_ARCHIVE_BYTES:
        raise IficFormatError("Larger than any expected IFIC archive")
    with artifact.open("rb") as handle:
        magic = handle.read(4)
    if magic[:2] != b"PK":
        if magic == b"\x00\x01\x00\x00":  # Jet database signature.
            yield artifact
            return
        raise IficFormatError("Neither a zip archive nor an Access database")
    with zipfile.ZipFile(artifact) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) != 1:
            raise IficFormatError("The archive must hold exactly one database")
        member = members[0]
        member_name = PurePosixPath(member.filename)
        if member_name.is_absolute() or ".." in member_name.parts or "\\" in member.filename:
            raise IficFormatError("Unsafe member name")
        if member_name.suffix.lower() != ".mdb":
            raise IficFormatError("The archive member is not an .mdb database")
        if member.file_size > MAX_DATABASE_BYTES:
            raise IficFormatError("The database is larger than the limit")
        if member.compress_size and member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
            raise IficFormatError("Compression ratio exceeds the limit")
        outer, inner = issue_from_name(name, kind), issue_from_name(member_name.name, kind)
        if inner is None:
            raise IficFormatError("The archive member is not named like an IFIC database")
        if outer is not None and outer != inner:
            raise IficFormatError("The database name does not match the archive issue")
        workdir = Path(tempfile.mkdtemp(prefix="astrasync-ific-"))
        try:
            target = workdir / "database.mdb"
            written = 0
            with archive.open(member) as source, target.open("wb") as sink:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > member.file_size or written > MAX_DATABASE_BYTES:
                        raise IficFormatError("The member is larger than declared")
                    sink.write(chunk)
            if written != member.file_size:
                raise IficFormatError("The member is shorter than declared")
            yield target
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


class _Tables:
    """Read-only table access. Each table is read once."""

    def __init__(self, path: Path) -> None:
        from access_parser import AccessParser

        try:
            self._db = AccessParser(str(path))
        except Exception as exc:  # noqa: BLE001 - any reader failure means an unreadable file.
            raise IficFormatError("Not a readable Access database") from exc
        self.names = {name for name in self._db.catalog if not name.startswith("MSys")}
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def rows(self, name: str) -> list[dict[str, Any]]:
        if name not in self._cache:
            if name not in self.names:
                raise IficFormatError(f"Table {name!r} is missing")
            try:
                columns = self._db.parse_table(name)
            except Exception as exc:  # noqa: BLE001
                raise IficFormatError(f"Table {name!r} could not be read") from exc
            keys = list(columns)
            count = len(columns[keys[0]]) if keys else 0
            self._cache[name] = [{key: columns[key][i] for key in keys} for i in range(count)]
        return self._cache[name]

    def require(self, *names: str) -> None:
        missing = sorted(set(names) - self.names)
        if missing:
            raise IficFormatError(f"Missing tables: {', '.join(missing)}")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _date(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return None if text.startswith("1900-01-01") else text[:10]


@dataclass
class _Record:
    table: str
    key: str
    raw: dict[str, str | None] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def flag(self, key: str, rule: str, severity: str = "WARNING", normalized: Any = None) -> None:
        self.findings.append(
            {
                "field_key": key,
                "raw_value": self.raw.get(key),
                "normalized_value": None if normalized is None else str(normalized),
                "rule_id": rule,
                "severity": severity,
            }
        )


def _status(findings: list[dict[str, Any]]) -> str:
    severities = {finding["severity"] for finding in findings}
    if "BLOCKING" in severities:
        return "REVIEW_REQUIRED"
    return "VALID_WITH_WARNINGS" if "WARNING" in severities else "VALID"


def _adapter_record(
    record: _Record,
    *,
    issue: int,
    notice_id: str | None,
    station: str | None,
    network: str | None,
    administration: str | None,
    start_mhz: float | None,
    end_mhz: float | None,
    schema: str,
    normalized: dict[str, Any],
    eligibility: dict[str, str],
) -> dict[str, Any]:
    raw = {key: value for key, value in record.raw.items()}
    # Normalised values travel in raw_fields under a reserved prefix as JSON-safe text, so the
    # record store keeps them beside the originals; the originals are never overwritten.
    for key, value in normalized.items():
        raw[f"norm.{key}"] = None if value is None else _norm_text(value)
    return {
        "source_table_or_sheet": record.table,
        "source_row_or_key": record.key,
        "source_page": None,
        "notice_id": notice_id,
        "issue_key": str(issue),
        "station_number": station,
        "network_id": network,
        "administration": administration,
        "frequency_start_mhz": start_mhz,
        "frequency_end_mhz": end_mhz,
        "record_status": _status(record.findings),
        "schema_version": schema,
        "raw_fields": raw,
        "field_aliases": {key: [key] for key in raw},
        "analysis_eligibility": eligibility,
        "quality_findings": record.findings,
        "reference_station": None,
    }


def _norm_text(value: Any) -> str:
    import json

    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


# --- Terrestrial --------------------------------------------------------------------------------


@dataclass
class IficSummary:
    """Counts used for reconciliation and for the evaluation report."""

    issue: int
    kind: str
    publication_date: str | None = None
    tables: int = 0
    counts: dict[str, Any] = field(default_factory=dict)


def read_terrestrial(
    path: Path, expected_issue: int | None = None
) -> tuple[list[dict[str, Any]], IficSummary]:
    db = _Tables(path)
    db.require("pub_current_circ", "pub", "fxm_terra", "fxm_pub_hist", "fxm_ant", "fxm_geo")
    current = db.rows("pub_current_circ")
    if len(current) != 1:
        raise IficFormatError("The database does not state one current circular")
    issue = int(current[0]["circ_no"])
    if expected_issue is not None and issue != expected_issue:
        raise IficFormatError("The database's own issue number does not match the file name")
    expected_issue = issue
    summary = IficSummary(expected_issue, TERRESTRIAL_SOURCE_TYPE, _date(current[0]["d_pub"]))
    summary.tables = len(db.names)

    pubs = {(r["pub_no"], r["pub_prefix"]): r["circ_no"] for r in db.rows("pub")}
    published: dict[Any, set[tuple[str, str]]] = defaultdict(set)
    for row in db.rows("fxm_pub_hist"):
        if pubs.get((row["pub_no"], row["pub_prefix"])) == expected_issue:
            published[row["terrakey"]].add((str(row["pub_prefix"]), str(row["pub_part"] or "")))
    antennas: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in db.rows("fxm_ant"):
        antennas[row["terrakey"]].append(row)
    geos = {row["geo_key"]: row for row in db.rows("fxm_geo")}
    tx_geo: dict[Any, Any] = {}
    if "fxm_tx" in db.names:
        for row in db.rows("fxm_tx"):
            tx_geo.setdefault(row["terrakey"], row["geo_key"])
    targets: dict[Any, list[tuple[Any, str]]] = defaultdict(list)
    if "fxm_target" in db.names:
        for row in db.rows("fxm_target"):
            targets[row["terrakey"]].append((row["target"], str(row["action"])))
    coordination: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    if "fxm_coord" in db.names:
        for row in db.rows("fxm_coord"):
            coordination[row["terrakey"]].append(row)
    classes = {}
    if "ref_stn_cls" in db.names:
        classes = {r["stn_cls"]: r["description"] for r in db.rows("ref_stn_cls")}

    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    parts: Counter[str] = Counter()
    for row in db.rows("fxm_terra"):
        terrakey = row["terrakey"]
        stage = _text(row.get("stage"))
        record = _Record("fxm_terra", str(terrakey))
        record.raw = {key: _text(value) for key, value in row.items()}
        role = "NOTICE" if stage == "NOTICE" else "RECORDED_CONTEXT"
        counts[f"rows.{role}"] += 1
        if role == "NOTICE":
            counts[f"intent.{row.get('intent')}"] += 1
            for prefix, part in published.get(terrakey, ()):
                parts[f"{prefix}:{part}"] += 1
            if not published.get(terrakey):
                record.flag("terrakey", "NOTICE_NOT_LISTED_IN_THIS_ISSUE", "WARNING")

        f_assign = _float(row.get("freq_assgn"))
        f_min, f_max = _float(row.get("freq_min")), _float(row.get("freq_max"))
        bandwidth_khz = _float(row.get("bdwdth"))
        if f_assign is None:
            record.flag("freq_assgn", "MISSING_ASSIGNED_FREQUENCY", "BLOCKING")
        start, end, basis = f_min, f_max, "NOTIFIED_FREQ_MIN_MAX"
        if start is None or end is None:
            if f_assign is not None and bandwidth_khz is not None:
                start = f_assign - bandwidth_khz / 2000
                end = f_assign + bandwidth_khz / 2000
                basis = "ASSIGNED_FREQUENCY_PLUS_MINUS_HALF_BANDWIDTH"
                record.flag("freq_min", "BAND_EDGES_DERIVED_FROM_BANDWIDTH", "INFO")
            elif f_assign is not None:
                start = end = f_assign
                basis = "ASSIGNED_FREQUENCY_ONLY"
                record.flag("bdwdth", "MISSING_BANDWIDTH", "WARNING")
        if start is not None and end is not None and start > end:
            record.flag("freq_min", "LOWER_EDGE_ABOVE_UPPER", "BLOCKING")
            start = end = None

        geo_key = row.get("geo_key") if row.get("geo_key") is not None else tx_geo.get(terrakey)
        geo = geos.get(geo_key)
        if geo is None:
            record.flag("geo_key", "MISSING_LOCATION", "WARNING")
        latitude = _float(geo.get("lat_dec")) if geo else None
        longitude = _float(geo.get("long_dec")) if geo else None
        if latitude is not None and not -90 <= latitude <= 90:
            record.flag("lat_dec", "LATITUDE_OUT_OF_RANGE", "BLOCKING")
            latitude = None
        if longitude is not None and not -180 <= longitude <= 180:
            record.flag("long_dec", "LONGITUDE_OUT_OF_RANGE", "BLOCKING")
            longitude = None

        tx_antennas = [a for a in antennas.get(terrakey, []) if _text(a.get("tx_rx")) != "RX"]
        antenna = tx_antennas[0] if tx_antennas else None
        power_dbw = _float(antenna.get("pwr_dbw")) if antenna else None
        power_type = POWER_TYPES.get(str(antenna.get("pwr_eiv"))) if antenna else None
        if antenna is None:
            record.flag("fxm_ant", "MISSING_TRANSMIT_ANTENNA", "WARNING")
        elif power_dbw is None:
            record.flag("pwr_dbw", "MISSING_RADIATED_POWER", "WARNING")
        elif power_type is None:
            record.flag("pwr_eiv", "UNKNOWN_POWER_TYPE", "WARNING")
        if len(tx_antennas) > 1:
            record.flag("fxm_ant", "SEVERAL_TRANSMIT_ANTENNAS_FIRST_USED", "INFO")

        normalized = {
            "role": role,
            "intent": _text(row.get("intent")),
            "stage": stage,
            "assignment_id": _text(row.get("assgn_id")),
            "adm_ref_id": _text(row.get("adm_ref_id")),
            "notice_type": _text(row.get("notice_typ")),
            "fragment": _text(row.get("fragment")),
            "provision": _text(row.get("prov")),
            "station_class": _text(row.get("stn_cls")),
            "station_class_description": classes.get(row.get("stn_cls")),
            "is_land_mobile": _text(row.get("stn_cls")) in LAND_MOBILE_CLASSES,
            "emission_class": _text(row.get("emi_cls")),
            "assigned_frequency_mhz": f_assign,
            "band_basis": basis,
            "bandwidth_khz": bandwidth_khz,
            "site_name": _text(geo.get("site_name")) if geo else None,
            "site_country": _text(geo.get("ctry")) if geo else None,
            "geo_type": _text(geo.get("geo_type")) if geo else None,
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "area_radius_km": _float(geo.get("radius")) if geo else None,
            "site_altitude_m": _float(geo.get("site_alt")) if geo else None,
            "radiated_power_dbw": power_dbw,
            "radiated_power_type": power_type,
            "power_designation": _text(antenna.get("pwr_xyz")) if antenna else None,
            "antenna_height_agl_m": _float(antenna.get("hgt_agl")) if antenna else None,
            "antenna_gain_max_db": _float(antenna.get("gain_max")) if antenna else None,
            "antenna_gain_type": GAIN_TYPES.get(str(antenna.get("gain_type"))) if antenna else None,
            "antenna_directivity": _text(antenna.get("ant_dir")) if antenna else None,
            "azimuth_max_radiation_deg": _float(antenna.get("azm_max_e")) if antenna else None,
            "beamwidth_deg": _float(antenna.get("bmwdth")) if antenna else None,
            "elevation_deg": _float(antenna.get("elev")) if antenna else None,
            "polarization": _text(antenna.get("polar")) if antenna else None,
            "max_circuit_length_km": _float(antenna.get("dist_max")) if antenna else None,
            "date_in_use": _date(row.get("d_inuse")),
            "date_received": _date(row.get("d_rcv")),
            "date_expiry": _date(row.get("d_expiry")),
            "targets": [[str(t), action] for t, action in targets.get(terrakey, [])],
            "coordination": [
                [_text(c.get("adm")), _text(c.get("coord_st")), _text(c.get("coord_prov"))]
                for c in coordination.get(terrakey, [])
            ],
            "publications": sorted(f"{p}:{part}" for p, part in published.get(terrakey, ())),
        }
        blocking = any(f["severity"] == "BLOCKING" for f in record.findings)
        records.append(
            _adapter_record(
                record,
                issue=expected_issue,
                notice_id=str(terrakey),
                station=_text(row.get("assgn_id")),
                network=None,
                administration=_text(row.get("adm")),
                start_mhz=start,
                end_mhz=end,
                schema=TERRESTRIAL_SCHEMA_VERSION,
                normalized=normalized,
                eligibility={
                    # RECORDED context rows are not screened: no relevance key.
                    **(
                        {}
                        if role != "NOTICE"
                        else {"FINLAND_RELEVANCE": "REVIEW_REQUIRED" if blocking else "VALID"}
                    ),
                    "TERR_P1546": (
                        "VALID"
                        if power_dbw is not None
                        and power_type is not None
                        and normalized["antenna_height_agl_m"] is not None
                        and latitude is not None
                        and longitude is not None
                        and f_assign is not None
                        else "INSUFFICIENT_DATA"
                    ),
                },
            )
        )
    # Notices of other services (broadcasting, LF/MF) are not parsed here, but are counted so
    # the total reconciles with the publisher's per-part notice counts in the issue's ReadMe.
    other_parts: Counter[str] = Counter()
    for table in ("fmtv_pub_hist", "lfmf_pub_hist"):
        if table in db.names:
            for row in db.rows(table):
                if pubs.get((row["pub_no"], row["pub_prefix"])) == expected_issue:
                    other_parts[f"{table.split('_')[0]}:{row['pub_prefix']}:{row['pub_part']}"] += 1
    summary.counts = {
        "other_service_publication_parts_not_parsed": dict(sorted(other_parts.items())),
        "fxm_terra_rows": len(db.rows("fxm_terra")),
        **dict(sorted(counts.items())),
        "publication_parts": dict(sorted(parts.items())),
        "records_out": len(records),
    }
    return records, summary


# --- Space --------------------------------------------------------------------------------------


def read_space(
    path: Path, expected_issue: int | None = None
) -> tuple[list[dict[str, Any]], IficSummary]:
    db = _Tables(path)
    db.require("notice", "grp", "s_beam", "emiss", "srv_cls")
    notices = db.rows("notice")
    issues: set[int] = {n["wic_no"] for n in notices if isinstance(n.get("wic_no"), int)}
    if not issues:
        raise IficFormatError("No notice states its IFIC number")
    # The database of an issue holds that issue's notices; their highest wic_no is the issue.
    issue: int = max(issues)
    if expected_issue is not None and issue != expected_issue:
        raise IficFormatError("The database's own issue number does not match the file name")
    in_issue = [n for n in notices if n.get("wic_no") == issue]
    if not in_issue:
        raise IficFormatError("No notice in the database belongs to the issue in the file name")
    summary = IficSummary(issue, SPACE_SOURCE_TYPE, _date(in_issue[0].get("d_wic")))
    summary.tables = len(db.names)

    names: dict[Any, dict[str, Any]] = {}
    for table in ("com_el", "geo", "non_geo"):
        if table in db.names:
            for row in db.rows(table):
                entry = names.setdefault(row["ntc_id"], {})
                for key in ("sat_name", "long_nom", "stn_name", "ctry"):
                    if row.get(key) is not None and entry.get(key) is None:
                        entry[key] = row[key]
    sections: dict[Any, list[str]] = defaultdict(list)
    if "pub_ssn" in db.names:
        for row in db.rows("pub_ssn"):
            sections[row["ntc_id"]].append(
                f"{row.get('ssn_ref')}/{row.get('ssn_no')}"
                + (f"/{row.get('ssn_rev')}{row.get('ssn_rev_no')}" if row.get("ssn_rev") else "")
            )
    orbits: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    if "orbit" in db.names:
        for row in db.rows("orbit"):
            orbits[row["ntc_id"]].append(row)
    earth: dict[Any, dict[str, Any]] = {}
    if "e_stn" in db.names:
        earth = {row["ntc_id"]: row for row in db.rows("e_stn")}
    pfd_limits: dict[Any, list[list[Any]]] = defaultdict(list)
    if "c_pfd" in db.names:
        for row in db.rows("c_pfd"):
            pfd_limits[row["ntc_id"]].append(
                [
                    _float(row["freq_min"]),
                    _float(row["freq_max"]),
                    _float(row["pfd"]),
                    _float(row["bdwdth"]),
                ]
            )

    wanted = {n["ntc_id"] for n in in_issue}
    beams = {
        (b["ntc_id"], b["emi_rcp"], b["beam_name"]): b
        for b in db.rows("s_beam")
        if b["ntc_id"] in wanted
    }
    groups = [g for g in db.rows("grp") if g["ntc_id"] in wanted]
    group_ids = {g["grp_id"] for g in groups}
    # A notice without frequency groups (for example a suppression) still gets one record, so
    # no notice of the issue can disappear from the screening.
    with_groups = {g["ntc_id"] for g in groups}
    groups += [
        {"grp_id": None, "ntc_id": n["ntc_id"], "_notice_only": True}
        for n in in_issue
        if n["ntc_id"] not in with_groups
    ]
    emissions: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in db.rows("emiss"):
        if row["grp_id"] in group_ids:
            emissions[row["grp_id"]].append(row)
    services: dict[Any, list[str]] = defaultdict(list)
    for row in db.rows("srv_cls"):
        if row["grp_id"] in group_ids:
            services[row["grp_id"]].append(f"{row.get('stn_cls')}/{row.get('nat_srv')}")
    areas: dict[Any, list[str]] = defaultdict(list)
    if "srv_area" in db.names:
        for row in db.rows("srv_area"):
            if row["grp_id"] in group_ids and row.get("ctry"):
                areas[row["grp_id"]].append(str(row["ctry"]))
    by_notice = {n["ntc_id"]: n for n in in_issue}

    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for notice in in_issue:
        counts[f"notice_type.{notice.get('ntc_type')}"] += 1
        for ref in sections.get(notice["ntc_id"], []):
            counts[f"special_section.{ref.split('/')[0]}"] += 1
    for group in groups:
        notice = by_notice[group["ntc_id"]]
        ntc_id = notice["ntc_id"]
        notice_only = bool(group.get("_notice_only"))
        record = _Record(
            "notice" if notice_only else "grp", str(ntc_id if notice_only else group["grp_id"])
        )
        record.raw = {} if notice_only else {f"grp.{k}": _text(v) for k, v in group.items()}
        record.raw.update({f"notice.{k}": _text(v) for k, v in notice.items()})
        start, end = _float(group.get("freq_min")), _float(group.get("freq_max"))
        if notice_only:
            record.flag("notice.ntc_id", "NO_FREQUENCY_GROUPS", "INFO")
        elif start is None or end is None:
            record.flag("grp.freq_min", "MISSING_BAND_EDGES", "BLOCKING")
            start = end = None
        elif start > end:
            record.flag("grp.freq_min", "LOWER_EDGE_ABOVE_UPPER", "BLOCKING")
            start = end = None
        beam = beams.get((ntc_id, group.get("emi_rcp"), group.get("beam_name")))
        if beam is None and not notice_only:
            record.flag("grp.beam_name", "BEAM_NOT_FOUND", "WARNING")
        group_emissions = emissions.get(group["grp_id"], [])
        pep = [v for v in (_float(e.get("pep_max")) for e in group_emissions) if v is not None]
        # A maximum power density (dBW/Hz) above the carrier's peak envelope power (dBW), or
        # below its own minimum density, cannot be right as published (a sign error, for
        # example). Such a value is excluded from calculations and reported, never corrected.
        density: list[float] = []
        anomalies: list[dict[str, Any]] = []
        for e in group_emissions:
            value = _float(e.get("pwr_ds_max"))
            if value is None:
                continue
            peak, low = _float(e.get("pep_max")), _float(e.get("pwr_ds_min"))
            problem = (
                "MAX_DENSITY_ABOVE_PEAK_POWER"
                if peak is not None and value > peak
                else "MAX_DENSITY_BELOW_MIN_DENSITY"
                if low is not None and value < low
                else None
            )
            if problem:
                anomalies.append(
                    {
                        "rule": problem,
                        "group_id": str(group["grp_id"]),
                        "emission": e.get("design_emi"),
                        "pwr_ds_max_dbw_hz": value,
                        "pwr_ds_min_dbw_hz": low,
                        "pep_max_dbw": peak,
                    }
                )
                record.flag("emiss.pwr_ds_max", problem, "WARNING", value)
            else:
                density.append(value)
        name = names.get(ntc_id, {})
        orbit_rows = orbits.get(ntc_id, [])
        apogees = [v for v in (_float(o.get("apog_km")) for o in orbit_rows) if v is not None]
        perigees = [v for v in (_float(o.get("perig_km")) for o in orbit_rows) if v is not None]
        inclinations = [
            v for v in (_float(o.get("inclin_ang")) for o in orbit_rows) if v is not None
        ]
        station = earth.get(ntc_id)
        gain = _float(beam.get("gain")) if beam else None
        transmit = _text(group.get("emi_rcp")) == "E"
        normalized = {
            "notice_id": str(ntc_id),
            "notice_type": NOTICE_TYPES.get(str(notice.get("ntc_type"))),
            "satellite_name": _text(name.get("sat_name")),
            "earth_station_name": _text(name.get("stn_name")),
            "earth_station_country": _text(name.get("ctry")),
            "network_organisation": _text(notice.get("ntwk_org")),
            "provision": _text(notice.get("prov")),
            "notification_reason": _text(notice.get("ntf_rsn")),
            "action_code": _text(notice.get("act_code")),
            # notice table (SNS v9.1): tgt_ntc_id = notice modified or suppressed; f_int_ext W/Z
            # = administration/BR withdrawal; ntf_occurs F = first submission.
            "target_notice_id": _text(notice.get("tgt_ntc_id")),
            "internal_external_flag": _text(notice.get("f_int_ext")),
            "submission_occurrence": _text(notice.get("ntf_occurs")),
            "ific_part": _text(notice.get("wic_part")),
            "date_received": _date(notice.get("d_rcv")),
            "special_sections": sorted(sections.get(ntc_id, [])),
            "nominal_longitude_deg": _float(name.get("long_nom")),
            "orbit_apogee_km_range": [min(apogees), max(apogees)] if apogees else None,
            "orbit_perigee_km_range": [min(perigees), max(perigees)] if perigees else None,
            "orbit_inclination_deg_range": (
                [min(inclinations), max(inclinations)] if inclinations else None
            ),
            "orbit_planes": len(orbit_rows) or None,
            "group_id": None if notice_only else str(group["grp_id"]),
            "direction": None if notice_only else "TRANSMIT" if transmit else "RECEIVE",
            "beam_name": _text(group.get("beam_name")),
            "bandwidth_khz": _float(group.get("bdwdth")),
            "noise_temperature_k": _float(group.get("noise_t")),
            "station_classes_services": sorted(set(services.get(group["grp_id"], []))),
            "service_area_countries": sorted(set(areas.get(group["grp_id"], []))),
            "emission_designations": sorted(
                {str(e["design_emi"]) for e in group_emissions if e.get("design_emi")}
            ),
            "max_peak_envelope_power_dbw": max(pep) if pep else None,
            "max_power_density_dbw_hz": max(density) if density else None,
            "power_anomalies": anomalies or None,
            "beam_max_gain_dbi": gain,
            "beam_peak_eirp_4khz_dbw": _float(beam.get("pwr_max_4k")) if beam else None,
            "beam_peak_eirp_1mhz_dbw": _float(beam.get("pwr_max_1m")) if beam else None,
            "group_ific": _float(group.get("wic_no")),
            "date_brought_into_use": _date(group.get("d_inuse")),
            "regulatory_finding": _text(group.get("fdg_reg")),
            "remark": _text(group.get("remark")),
            "earth_station_latitude_deg": _float(station.get("lat_dec")) if station else None,
            "earth_station_longitude_deg": _float(station.get("long_dec")) if station else None,
            "notified_pfd_limits": pfd_limits.get(ntc_id) or None,
        }
        if transmit and not density:
            record.flag("emiss.pwr_ds_max", "MISSING_POWER_DENSITY", "WARNING")
        if transmit and gain is None:
            record.flag("s_beam.gain", "MISSING_ANTENNA_GAIN", "WARNING")
        pfd_ready = (
            transmit
            and normalized["notice_type"] in ("GSO_SPACE_STATION", "NON_GSO_SPACE_STATION")
            and bool(density)
            and gain is not None
        )
        blocking = any(f["severity"] == "BLOCKING" for f in record.findings)
        records.append(
            _adapter_record(
                record,
                issue=issue,
                notice_id=str(ntc_id),
                station=_text(name.get("stn_name")),
                network=_text(name.get("sat_name")),
                administration=_text(notice.get("adm")),
                start_mhz=start,
                end_mhz=end,
                schema=SPACE_SCHEMA_VERSION,
                normalized=normalized,
                eligibility={
                    "FINLAND_RELEVANCE": "REVIEW_REQUIRED" if blocking else "VALID",
                    "SPACE_PFD_FREE_SPACE": "VALID" if pfd_ready else "INSUFFICIENT_DATA",
                },
            )
        )
        counts["groups"] += 1
    summary.counts = {
        "notices_in_database": len(notices),
        "notices_in_issue": len(in_issue),
        **dict(sorted(counts.items())),
        "records_out": len(records),
    }
    return records, summary


# --- SourceAdapter wrappers ---------------------------------------------------------------------


class _IficAdapter:
    kind = ""

    def _read(self, path: Path, issue: int | None) -> tuple[list[dict[str, Any]], IficSummary]:
        raise NotImplementedError

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int, original_name: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        name = original_name or artifact_path.name
        issue = issue_from_name(name, self.kind)
        with open_database(artifact_path, self.kind, name) as database:
            records, _ = self._read(database, issue)
        for start in range(0, len(records), batch_rows):
            yield records[start : start + batch_rows]


class ItuSpaceIficAdapter(_IficAdapter):
    """``SourceAdapter`` for one Space IFIC database (SNS v10)."""

    source_type = SPACE_SOURCE_TYPE
    parser_version = SPACE_PARSER_VERSION
    kind = SPACE_SOURCE_TYPE

    def _read(self, path: Path, issue: int | None) -> tuple[list[dict[str, Any]], IficSummary]:
        return read_space(path, issue)


class ItuTerrestrialIficAdapter(_IficAdapter):
    """``SourceAdapter`` for one Terrestrial BR IFIC MDB extract."""

    source_type = TERRESTRIAL_SOURCE_TYPE
    parser_version = TERRESTRIAL_PARSER_VERSION
    kind = TERRESTRIAL_SOURCE_TYPE

    def _read(self, path: Path, issue: int | None) -> tuple[list[dict[str, Any]], IficSummary]:
        return read_terrestrial(path, issue)
