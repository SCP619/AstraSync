# Space IFIC 3074: results summary

**Data status: REAL** ITU Space IFIC 3074 (SNS v10 database, published 23.06.2026), compared with
3073; Finnish references: Traficom M4 (live open data) and the challenge workbook (synthetic
stations). Produced by `astrasync_data.ific_evaluate` at commit `8e0f105` (manifest generated
2026-11-08T07:10:02Z) and reproduced from that commit on 2026-11-08 with identical results.

**Completeness:** every notice is screened, but **no RR Article 21 PFD limit is applied** (the
complete authoritative Table 21-4 was not obtained; decision C10). Results are therefore ranked
screenings with PFD **upper bounds**; there are **no limits, margins or exceedance classes** for
space. Treat these as incomplete for regulatory accuracy evaluation.

## Files

| File | Content |
| --- | --- |
| `findings.csv` | One row per notice (196), ranked: notice ID, administration, type, satellite, special sections, change, geometry, groups, downlink groups on special-interest frequencies, maximum PFD upper bound, priority score, tier, status |
| `space_ific_3074_results.xlsx` | The same results with About, Results and Inputs sheets |
| `findings_high.json` | The HIGH-tier finding with every stage, group, calculation, input, assumption and hash |
| `findings.json.gz` | All 196 findings, full detail (gzip JSON) |
| `comparison.json` | Change types against 3073 and the rules used |
| `manifest.json` | Inputs (official URLs, SHA-256), parser, rule and method versions with implementation hashes, screening parameters |
| `report.md` | Human-readable report: reconciliation, changes, ranked items with reasons, anomalies, limitations |

## Numbers

| Measure | Value |
| --- | --- |
| Notices | 196 (72 GSO, 112 non-GSO, 12 specific earth stations) |
| Records | 34,367 (34,365 frequency groups + 2 notices without groups, kept so nothing disappears) |
| Special-section links | API 72, CR 148, RES49 5 |
| Change vs 3073 | 96 NEW, 55 MODIFIED, 45 INDETERMINATE |
| Geometry | 92 NGSO reach Finnish latitudes, 35 GSO visible, 37 GSO not visible, 8 NGSO do not reach, 12 earth stations, 12 unknown |
| Status | 1 EXPERT_REVIEW_REQUIRED, 117 SCREENED_LOW_PRIORITY, 33 INSUFFICIENT_DATA, 45 SCREENED_OUT_GEOMETRY |
| Priority tiers | 1 HIGH, 111 MEDIUM, 84 LOW |

## Highest-ranked notices

| Rank | Adm. | Network | Sections | Change | Downlink groups on special-interest freq. | PFD upper bound dB(W/m²) in 1 Hz | Tier |
| ---: | --- | --- | --- | --- | ---: | ---: | --- |
| 1 | D | SOLAR SENTRY (NGSO) | API/A/14387 | NEW | 2 | −165.94 | HIGH |
| 2 | CHN | CSN-SSO | API/A/13924/M1, API/B/3487 | NEW | 55 | −112.84 | MEDIUM |
| 3 | E | PAZ_2-A | CR/C/6322, CR/D/5376 | MODIFIED | 1 | −122.81 | MEDIUM |
| 4 | CHN | GY-2 | API/A/14233, API/B/3501 | NEW | 3 | −124.68 | MEDIUM |
| 5 | CHN | YG-1 | API/A/14388 | NEW | 10 | −128.10 | MEDIUM |

SOLAR SENTRY is the only HIGH item because its notified service area includes Finland (+3) on top
of a special-interest frequency overlap, Finnish visibility and a new API/A publication.

## Data-quality anomaly (published data)

IND LVI (notice `126545057`), group 126662625, emission 8M00G2D: `pwr_ds_max` **+73.0 dBW/Hz**
with `pwr_ds_min` −76.0 dBW/Hz and `pep_max` −4.0 dBW. A maximum density above the carrier's peak
power is impossible as published (likely a sign error). Excluded from calculations; a candidate
for a request for clarification.

Method: [`SPACE_METHODOLOGY.md`](SPACE_METHODOLOGY.md). Worked example:
[`../04_Input_Output/INPUT_OUTPUT_GUIDE.md`](../04_Input_Output/INPUT_OUTPUT_GUIDE.md#worked-example-space).
