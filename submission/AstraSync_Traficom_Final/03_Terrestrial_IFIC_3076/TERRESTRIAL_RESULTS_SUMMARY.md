# Terrestrial IFIC 3076: results summary

**Data status: REAL** ITU BR IFIC (Terrestrial Services) 3076 MDB extract (published 21.07.2026),
compared with 3075; Finnish references: Traficom M4 (live open data) and the challenge workbook
(synthetic stations). Produced by `astrasync_data.ific_evaluate` at commit `8e0f105` (manifest
generated 2026-11-08T07:04:37Z) and reproduced from that commit on 2026-11-08 with identical
results. Criterion: ECC Recommendation T/R 25-08, Edition 6 June 2025, Annex 1 A1.2.3.

## Files

| File | Content |
| --- | --- |
| `findings.csv` | One row per land-mobile notice (1,867), ranked: IDs, administration, station class, site, frequency, bandwidth, change, distance to Finland, workbook overlaps, maximum field strength, **border/territorial-sea maximum and its location**, points evaluated, criterion basis, base threshold, bandwidth correction, **threshold, margin, concern class**, coordination, priority |
| `terrestrial_ific_3076_cases.json` | The 6 notices above the threshold, each with all stage results, calculations, border screening, cited criterion and coordination rows |
| `border_points.csv` | The five strongest boundary points per notice (lat/lon, distance, field strength, threshold, margin, calculation SHA-256) |
| `terrestrial_ific_3076_results.xlsx` | About, Results, Border points and Inputs sheets |
| `findings_high.json`, `findings.json.gz` | HIGH-tier and all findings, full detail |
| `comparison.json` | Changes vs 3075 and neighbouring-administration activity trends |
| `manifest.json`, `report.md` | Provenance and the human-readable report |

## Reconciliation with the ITU Information Note (ReadMe) for 3076

| ReadMe | Parsed (fixed/mobile) | Broadcasting tables (counted) | Total |
| --- | ---: | ---: | ---: |
| Article 11 Part I: 2,415 | 2,404 | 11 | 2,415 |
| Part II: 1,051 | 1,051 | 0 | 1,051 |
| Part III: 44 | 10 | 34 | 44 |
| GE06L/167 A+B: 2+14 | 2+14 | — | 16 |
| GE84/365 A+B: 406+66 | — | 406+66 | 472 |

All 4,057 fixed/mobile rows were parsed (3,481 notices, 576 recorded assignments they target).
Scope of the side quest: the 1,867 land-mobile notices (station classes FB, ML, FL). Changes vs
3075: 1,856 NEW, 11 MODIFIED (with field-level differences).

## Classification of the 1,867 notices

| Class | Count | Meaning |
| --- | ---: | --- |
| VERIFIED_CRITERION_EXCEEDANCE | 1 | Field strength above the T/R 25-08 threshold at a Finnish border or territorial-sea point; coordination with Finland indicated |
| COORDINATION_REVIEW | 5 | Above the threshold and Finland is named in the notice's coordination data: expert review, never "settled" |
| POTENTIAL_CONCERN | 0 | Within 6 dB below the threshold |
| BELOW_SCREENING_THRESHOLD | 42 | Calculated, more than 6 dB below |
| FREQUENCY_OVERLAP_ONLY | 534 | Overlaps Finnish use but no border calculation possible |
| INSUFFICIENT_EVIDENCE | 1,285 | Missing inputs, beyond P.1546 scope (> 1000 km, outside 30–4000 MHz) or no criterion |

## Notices above the threshold

All Russian base stations (FB), maximum at the Finland–Russia land border, 10 % time, 50 %
locations, 10 m receiver. Threshold for 108–380 MHz: 12 dB(µV/m); notified 16.8 kHz is below the
25 kHz reference, so no bandwidth correction.

| Rank | Notice | Assignment | Site | MHz | Border E dB(µV/m) | Threshold | Margin dB | Class | Finland in coordination |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 93082383 | 126080966 | KRL KOSTOMUKSHA | 152.025 | 26.836 | 12.0 | +14.84 | COORDINATION_REVIEW | yes |
| 2 | 93082838 | 126081421 | KRL KOSTOMUKSHA | 152.900 | 26.532 | 12.0 | +14.53 | COORDINATION_REVIEW | yes |
| 3 | 93075637 | 126074220 | KRL LYASKELYA | 152.900 | 20.883 | 12.0 | +8.88 | VERIFIED_CRITERION_EXCEEDANCE | no |
| 4 | 93082322 | 126080905 | LEN VYBORG GRUZOVOI | 153.075 | 20.110 | 12.0 | +8.11 | COORDINATION_REVIEW | yes |
| 5 | 93082324 | 126080907 | LEN VYBORG GRUZOVOI | 153.025 | 20.110 | 12.0 | +8.11 | COORDINATION_REVIEW | yes |
| 9 | 93082323 | 126080906 | LEN VYBORG GRUZOVOI | 153.300 | 20.106 | 12.0 | +8.11 | COORDINATION_REVIEW | yes |

An exceedance of this indicative coordination threshold means coordination with Finland is
indicated under the stated screening assumptions (no terrain, heff = ha, maximum-radiation
direction). It is **not** harmful interference and **not** non-compliance.

Method: [`TERRESTRIAL_METHODOLOGY.md`](TERRESTRIAL_METHODOLOGY.md). Worked example:
[`../04_Input_Output/INPUT_OUTPUT_GUIDE.md`](../04_Input_Output/INPUT_OUTPUT_GUIDE.md#worked-example-terrestrial).
