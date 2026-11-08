# IFIC pipeline: acquisition, parsing, relevance, calculations, evaluation

Status as of 2026-11-08. Decisions: `traficom-integration/contract/DECISIONS.md` G27 (IFIC issue
analysis) and G28 (drafting agents). Evaluation outputs for the mandatory issues:
[`evaluation/`](../../evaluation/README.md).

## 1. Source coverage

| Source | URL | Access | Licence / restriction | Format | Parser | Issues available | Refresh | Verified |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Space IFIC (SNS v10 database) | https://www.itu.int/sns/wic/demowic.html → `https://www.itu.int/sns/ific10/ific<N>.zip` | Public HTTPS, no login | "Free service on a trial basis until further notice" (ITU page); older years only on the sold BR IFIC DVD | ZIP of one MS Access `.mdb` (SNS v10) | `astrasync_data.itu_ific:ItuSpaceIficAdapter` | Year pages 1998–2026; the page states files from previous years are no longer supported online | `ItuSpaceIficClient` reads the current and previous year pages; range `ASTRASYNC_ITU_SPACE_ISSUES` | Real data: 3074 and 3073 downloaded, parsed, analysed |
| Terrestrial BR IFIC MDB extract | https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx → `/BRIFIC/MDB/brific<N>.zip` | Public HTTPS, no login | Extract only; the full BR IFIC (all data and software) is the ITU-sold DVD/ISO | ZIP of one `.mdb` | `ItuTerrestrialIficAdapter` | Page lists the latest ten (3074–3083 on 2026-11-08) | `ItuTerrestrialIficClient`; range `ASTRASYNC_ITU_TERRESTRIAL_ISSUES` | Real data: 3076 and 3075 downloaded, parsed, analysed; reconciled with the ITU ReadMe |
| Traficom M4 table | https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko | Public API | CC BY 4.0 | JSON (OData) | `TraficomM4TableAdapter` | One current snapshot (ETag versioned) | `TraficomFrequencyTableClient` | Real data: 5,917 rows |
| Special-interest workbook | Challenge platform | Provided to participants | Synthetic; kept out of git | XLSX | `TraficomWorkbookAdapter` | v05112026 | Manual upload | Real file: 874 rows |
| M15, CEPT/ECC, RR, ITU-R Recs | Finlex, docdb.cept.org, itu.int | Public documents | Various | PDF/HTML | None (reference documents) | — | — | Not machine-ingested: criteria must be entered and approved by hand (A43) |

Downloads go only to `www.itu.int` and `opendata.traficom.fi`, over HTTPS, with redirects
refused, a size limit and a SHA-256 of the received bytes (`acquisition.download_to_file`). Index
pages are parsed with fixed patterns; a page listing nothing is a source failure, never an empty
source, and an outage never marks anything withdrawn.

## 2. Parsing (`astrasync-core-lib/data/astrasync_data/itu_ific.py`)

- Archive: exactly one `.mdb` member, safe name, issue number matching, ≤ 4 GiB, compression
  ratio ≤ 200, extracted to a private temporary folder and removed afterwards. Anything else is
  refused (the artifact is quarantined). Reader: `access-parser` (pure Python, Apache-2.0),
  inside the existing parser sandbox process (A16).
- Issue number: from the database (`pub_current_circ` terrestrial; notices' `wic_no` space),
  cross-checked with the file name when there is one.
- Field meanings: Terrestrial BR IFIC Preface data dictionary (units: frequency MHz, bandwidth
  kHz, radius km, height m, power dBW; `pwr_eiv` I/E/V = e.i.r.p./e.r.p./e.m.r.p.; `gain_type`
  I/D/V). Space: SNS data items v9.1 (`pwr_ds_max` dBW/Hz, `pep_max` dBW, beam `gain` dBi,
  `freq_min/max` MHz, `bdwdth` kHz). ITU publishes no v10 dictionary; fields whose v10 meaning
  might differ are kept raw.
- Every record keeps all original columns as text, the normalised values (`norm.*`) beside them,
  table and key, and field-level quality findings. Nothing is imputed.
- Terrestrial records: one per `fxm_terra` row — NOTICE rows of the issue, plus RECORDED rows that
  a MODIFY/SUPPRESS targets (context only, never screened).
- Space records: one per frequency group (`grp`) of every notice of the issue, plus one record for
  a notice without groups, so no notice can disappear.
- Plausibility rule (space): a maximum power density above the carrier's peak envelope power, or
  below its own minimum, is excluded from calculations and reported (`MAX_DENSITY_ABOVE_PEAK_POWER`).
  3074 has one: IND LVI, group 126662625, `pwr_ds_max` +73.0 dBW/Hz with `pep_max` −4.0 dBW.

### Reconciliation

Terrestrial 3076 against the ITU Information Note (ReadMe) for the issue:

| ReadMe count | Parsed (fixed/mobile tables) | Broadcasting tables (counted, not parsed) | Total |
| --- | ---: | ---: | ---: |
| Article 11, Part I: 2415 | 2404 | 11 | 2415 |
| Part II: 1051 | 1051 | 0 | 1051 |
| Part III: 44 | 10 | 34 | 44 |
| GE06L/167 A + B: 2 + 14 | 2 + 14 | — | 16 |
| GE84/365 A + B: 406 + 66 | — | 406 + 66 | 472 |

All 4,057 `fxm_terra` rows become records (3,481 notices + 576 recorded targets). Space 3074:
196 notices (72 GSO, 112 NGSO, 12 specific earth stations), 34,365 frequency groups, every notice
present in the output.

## 3. Change detection

From the publication itself, never from absence:

- Terrestrial: `intent` ADD → NEW, MODIFY → MODIFIED (field-level differences against the targeted
  RECORDED row in the same extract), SUPPRESS/WITHDRAW → WITHDRAWN. The previous issue is matched
  by assignment ID for context.
- Space: `f_int_ext` W/Z → WITHDRAWN; `tgt_ntc_id` ≠ own ID → MODIFIED; `ntf_occurs` F or a
  Special Section API/A without target → NEW; otherwise INDETERMINATE (the raw `act_code` is kept).

Each IFIC carries that issue's notices only, so an item missing from a later issue is not treated
as withdrawn.

## 4. Finland relevance (`ific_analysis.py`)

| Stage | Terrestrial (land mobile FB/ML/FL) | Space |
| --- | --- | --- |
| A Frequency | Closed-interval overlap with M4 sub-bands and special-interest stations (centre ± half channel) | Same, per frequency group |
| B Service | Finnish MOBILE / LAND MOBILE allocation in the band; same station class in Finland | Downlink in a band where Finland has a terrestrial service; service area includes FIN |
| C Geography / orbit | Great-circle distance to the Natural Earth Finland boundary (mobile areas reduced by their radius) | GSO elevation from Hanko, Helsinki, Joensuu, Utsjoki; NGSO reach of 59.7–70.1° N from inclination and altitude; earth station distance |
| D Readiness | P.1546 inputs present (e.r.p. or e.i.r.p., height, coordinates, 30–4000 MHz, ≤ 1000 km) | Power density, beam gain and geometry present |
| E Priority | Additive score, listed per finding; HIGH ≥ 7 | Additive score; HIGH ≥ 10 (needs a service area including Finland) |

Relevance, readiness, priority and any regulatory finding are kept apart. With no approved
criterion the strongest status is `EXPERT_REVIEW_REQUIRED`. Cases are opened for HIGH findings.

## 5. Calculations

| Method | Implementation | Validation | Use here |
| --- | --- | --- | --- |
| `TERR_P1546` (ITU-R P.1546-6) | Python port of the ITU-R WP 3K reference `P1546FieldStrMixed.m` v16; curves extracted unchanged | All 54 reference validation logs reproduced, max deviation 5.1e-5 dB (`tests/test_p1546.py`, run with `ASTRASYNC_P1546_REFERENCE`) | Field strength at the nearest point of Finland (10 % time, 50 % locations, 10 m, rural) and at overlapping special-interest stations; heff = ha (no terrain data); land/sea zones from Natural Earth |
| `SPACE_PFD_FREE_SPACE` | Inverse-square law (P.525 context) | Analytic unit tests | Upper bound per 1 Hz: notified maximum power density + maximum beam gain at the minimum slant range |
| EPFD, directional PFD, P.1812, P.452 | Not implemented | — | Catalogued as candidates only |

## 6. Running it

```bash
python -m astrasync_data.ific_evaluate terrestrial --issue brific3076.zip --previous brific3075.zip --m4 Taajuusjakotaulukko-v13.json --workbook Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx --out evaluation/terrestrial_3076
```

In the platform: register the sources (connector `endpoint_ref` `itu-space-ific`,
`itu-terrestrial-ific`, `traficom-m4`), configure `ASTRASYNC_SOURCE_CLIENTS`,
`ASTRASYNC_SOURCE_ADAPTERS` and `ASTRASYNC_RF_METHODS` as in `tests/support/dev_stack.py`
(`REAL_ENVIRONMENT`), and check the sources. Indexing an IFIC issue queues its RELEVANCE job.
