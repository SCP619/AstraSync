# AstraSync evaluation: Terrestrial IFIC 3076

Publication date (from the database): 2026-07-21. Generated 2026-11-08T07:04:37+00:00 by rule set `ific-finland-relevance/1.0.0`.

**What this is.** A deterministic screening of every notice in the issue against Finnish frequency use (M4 table and the challenge's special-interest stations), with explainable priorities and, where the notice holds the inputs, technical calculations. **Criterion.** Land-mobile notices are screened along Finland's land borders and territorial-sea outer limit with ITU-R P.1546-6 (10 % time, 50 % locations, 10 m) against the indicative coordination thresholds of ECC T/R 25-08 A1.2.3 (edition 6 June 2025), applied above 470 MHz as a challenge extension approved by the organizers. An exceedance indicates coordination with Finland; it is not harmful interference or non-compliance. Every flagged item needs expert review.

## Inputs

| Role | File | Bytes | SHA-256 | Source |
| --- | --- | ---: | --- | --- |
| IFIC issue | `brific3076.zip` | 2406450 | `ba9d0605a4a54941…` | https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3076.zip |
| previous IFIC issue | `brific3075.zip` | 3427636 | `6f63a3dee548422c…` | https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3075.zip |
| Finnish table of frequencies (M4), Traficom open data, CC BY 4.0 | `Taajuusjakotaulukko-v13.json` | 4359860 | `41ffdd0ed84a40c1…` | https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko |
| Challenge special-interest workbook (synthetic data) | `Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx` | 100809 | `bb7f481f085fb6c4…` | challenge platform |

## Parse and reconciliation

```json
{
 "other_service_publication_parts_not_parsed": {
  "fmtv:GE84:A": 406,
  "fmtv:GE84:B": 66,
  "fmtv:NTFD_RR:1": 11,
  "fmtv:NTFD_RR:3": 34
 },
 "fxm_terra_rows": 4057,
 "intent.ADD": 2905,
 "intent.MODIFY": 163,
 "intent.SUPPRESS": 413,
 "rows.NOTICE": 3481,
 "rows.RECORDED_CONTEXT": 576,
 "publication_parts": {
  "GE06L:A": 2,
  "GE06L:B": 14,
  "NTFD_RR:1": 2404,
  "NTFD_RR:2": 1051,
  "NTFD_RR:3": 10
 },
 "records_out": 4057
}
```

## Changes against the previous issue

```json
{
 "issue": 3076,
 "previous_issue": 3075,
 "change_types": {
  "NEW": 1856,
  "MODIFIED": 11
 },
 "also_published_in_previous_issue": 0
}
```

NEW, MODIFIED and WITHDRAWN come from the notice itself (terrestrial intent ADD/MODIFY/SUPPRESS; space ntf_occurs, tgt_ntc_id, f_int_ext). An item absent from an issue is never treated as withdrawn: each IFIC carries that issue's notices only.

## Results

Notices screened: 1867. Priority tiers: {"HIGH": 20, "MEDIUM": 38, "LOW": 1809}. Statuses: {"EXPERT_REVIEW_REQUIRED": 15, "INSUFFICIENT_DATA": 9, "SCREENED_LOW_PRIORITY": 1843}.

### Method and assumptions

- Scope: land mobile notices (station classes FB, ML, FL) published in this issue.
- A: overlap with M4 sub-bands and special-interest station intervals (centre ± half channel). B: Finnish MOBILE / LAND MOBILE allocation in the band. C: great-circle distance to Finland's boundary. D: P.1546 inputs present.
- Field strength: ITU-R P.1546-6 (port validated against the ITU-R WP 3K reference implementation, 54 cases, max deviation 5.1e-5 dB), 10.0 % time, 50.0 % locations, receiver 10.0 m (or the special-interest station's antenna height), rural, heff = ha (no terrain data), land/sea zones from Natural Earth, maximum e.r.p. (no antenna pattern).
- Priority score components are listed per finding in `findings.json.gz`; tiers: HIGH ≥ 7, MEDIUM ≥ 4. Priority is for ordering expert work; it is not a statement of concern.

### Highest-priority items

- **RUS FB KRL KOSTOMUKSHA** — notice `93082383` (assignment 126080966, NTFD_RR:1), 152.025 MHz / 16.8 kHz, NEW; 28.45 km from Finland; 1 special-interest overlaps; 26.8 dB(µV/m) at Nearest point of Finland (P.1546-6, 28.5 km). Score 13 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available, coordination_threshold_exceeded. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB KRL KOSTOMUKSHA** — notice `93082838` (assignment 126081421, NTFD_RR:1), 152.9 MHz / 16.8 kHz, NEW; 28.92 km from Finland; 4 special-interest overlaps; 26.5 dB(µV/m) at Nearest point of Finland (P.1546-6, 28.9 km). Score 13 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available, coordination_threshold_exceeded. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB KRL LYASKELYA** — notice `93075637` (assignment 126074220, NTFD_RR:2), 152.9 MHz / 16.8 kHz, NEW; 42.66 km from Finland; 4 special-interest overlaps; 24.0 dB(µV/m) at Station 614221 TX (P.1546-6, 56.9 km). Score 13 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available, coordination_threshold_exceeded. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB LEN VYBORG GRUZOVOI** — notice `93082322` (assignment 126080905, NTFD_RR:1), 153.075 MHz / 16.8 kHz, NEW; 30.32 km from Finland; 1 special-interest overlaps; 21.4 dB(µV/m) at Station 601062 TX (P.1546-6, 49.2 km). Score 13 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available, coordination_threshold_exceeded. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB LEN VYBORG GRUZOVOI** — notice `93082324` (assignment 126080907, NTFD_RR:1), 153.025 MHz / 16.8 kHz, NEW; 30.32 km from Finland; 1 special-interest overlaps; 19.9 dB(µV/m) at Station 626855 TX (P.1546-6, 54.6 km). Score 13 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available, coordination_threshold_exceeded. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB KRL RUSKEALA** — notice `93082392` (assignment 126080975, NTFD_RR:1), 793.5 MHz / 5000.0 kHz, MODIFIED; 14.65 km from Finland; 1 special-interest overlaps; 31.8 dB(µV/m) at Nearest point of Finland (P.1546-6, 14.7 km). Score 10 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB KRL RUSKEALA** — notice `93005610` (assignment 126004193, GE06L:B), 793.5 MHz / 5000.0 kHz, NEW; 13.57 km from Finland; 1 special-interest overlaps; 22.4 dB(µV/m) at Nearest point of Finland (P.1546-6, 13.6 km). Score 10 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB KRL RUSKEALA** — notice `93005611` (assignment 126004194, GE06L:B), 794.74 MHz / 7200.0 kHz, NEW; 13.57 km from Finland; 2 special-interest overlaps; 22.4 dB(µV/m) at Nearest point of Finland (P.1546-6, 13.6 km). Score 10 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB LEN VYBORG GRUZOVOI** — notice `93082323` (assignment 126080906, NTFD_RR:1), 153.3 MHz / 16.8 kHz, NEW; 30.32 km from Finland; 0 special-interest overlaps; 19.9 dB(µV/m) at Nearest point of Finland (P.1546-6, 30.3 km). Score 10 (HIGH): change_new_or_modified, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available, coordination_threshold_exceeded. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB MUR TITOVKA** — notice `93082397` (assignment 126080980, NTFD_RR:1), 793.5 MHz / 5000.0 kHz, NEW; 94.7 km from Finland; 1 special-interest overlaps; -13.8 dB(µV/m) at Nearest point of Finland (P.1546-6, 94.7 km). Score 10 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB MUR TITOVKA** — notice `93082398` (assignment 126080981, NTFD_RR:1), 794.74 MHz / 7200.0 kHz, NEW; 94.7 km from Finland; 2 special-interest overlaps; -13.8 dB(µV/m) at Nearest point of Finland (P.1546-6, 94.7 km). Score 10 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS ML KRL LYASKELYA** — notice `93075638` (assignment 126074221, NTFD_RR:2), 152.9 MHz / 16.8 kHz, NEW; 42.66 km from Finland; 4 special-interest overlaps; no calculation. Score 9 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration. Status INSUFFICIENT_DATA.
- **RUS ML KRL KOSTOMUKSHA** — notice `93082321` (assignment 126080904, NTFD_RR:1), 152.9 MHz / 16.8 kHz, NEW; 28.92 km from Finland; 4 special-interest overlaps; no calculation. Score 9 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration. Status INSUFFICIENT_DATA.
- **RUS FB LEN KINGISEPP** — notice `93075624` (assignment 126074207, NTFD_RR:2), 425.825 MHz / 18.0 kHz, MODIFIED; 125.01 km from Finland; 1 special-interest overlaps; 17.1 dB(µV/m) at Station 640513 TX (P.1546-6, 147.5 km). Score 8 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB LEN KINGISEPP** — notice `93075629` (assignment 126074212, NTFD_RR:2), 424.475 MHz / 18.0 kHz, MODIFIED; 141.2 km from Finland; 1 special-interest overlaps; 9.9 dB(µV/m) at Station 606465 TX (P.1546-6, 171.5 km). Score 8 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB LEN KINGISEPP** — notice `93075627` (assignment 126074210, NTFD_RR:2), 424.075 MHz / 18.0 kHz, MODIFIED; 141.2 km from Finland; 1 special-interest overlaps; 6.9 dB(µV/m) at Nearest point of Finland (P.1546-6, 141.2 km). Score 8 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS FB LEN PROMZONA** — notice `93005612` (assignment 126004195, GE06L:B), 794.74 MHz / 7200.0 kHz, NEW; 131.6 km from Finland; 2 special-interest overlaps; -10.9 dB(µV/m) at Nearest point of Finland (P.1546-6, 131.6 km). Score 8 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration, calculation_available. Status EXPERT_REVIEW_REQUIRED.
- **RUS ML LEN KINGISEPP** — notice `93075625` (assignment 126074208, NTFD_RR:2), 415.825 MHz / 18.0 kHz, MODIFIED; 125.01 km from Finland; 1 special-interest overlaps; no calculation. Score 7 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration. Status INSUFFICIENT_DATA.
- **RUS ML LEN KINGISEPP** — notice `93075628` (assignment 126074211, NTFD_RR:2), 414.075 MHz / 18.0 kHz, MODIFIED; 141.2 km from Finland; 1 special-interest overlaps; no calculation. Score 7 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration. Status INSUFFICIENT_DATA.
- **RUS ML LEN KINGISEPP** — notice `93075630` (assignment 126074213, NTFD_RR:2), 414.475 MHz / 18.0 kHz, MODIFIED; 141.2 km from Finland; 1 special-interest overlaps; no calculation. Score 7 (HIGH): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration. Status INSUFFICIENT_DATA.
- **RUS ML KRL KOSTOMUKSHA** — notice `93082382` (assignment 126080965, NTFD_RR:1), 155.6 MHz / 16.8 kHz, NEW; 28.92 km from Finland; 0 special-interest overlaps; no calculation. Score 6 (MEDIUM): change_new_or_modified, finnish_land_mobile_allocation, within_100_km_of_finland, within_300_km_of_finland, neighbouring_administration. Status INSUFFICIENT_DATA.
- **RUS FB PSK PSKOV** — notice `93075616` (assignment 126074199, NTFD_RR:2), 154.6 MHz / 11.0 kHz, NEW; 300.0 km from Finland; 0 special-interest overlaps; -25.3 dB(µV/m) at Nearest point of Finland (P.1546-6, 300.0 km). Score 5 (MEDIUM): change_new_or_modified, finnish_land_mobile_allocation, within_300_km_of_finland, neighbouring_administration, calculation_available. Status SCREENED_LOW_PRIORITY.
- **RUS FB PSK PYTALOVO** — notice `93081456` (assignment 126080039, GE06L:A), 803.5 MHz / 5000.0 kHz, NEW; 367.45 km from Finland; 3 special-interest overlaps; -28.4 dB(µV/m) at Nearest point of Finland (P.1546-6, 367.4 km). Score 5 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, neighbouring_administration, calculation_available. Status SCREENED_LOW_PRIORITY.
- **POL FB OSR0102** — notice `92817515` (assignment 124021622, GE06L:B), 803.5 MHz / 5000.0 kHz, NEW; 677.13 km from Finland; 3 special-interest overlaps; -32.2 dB(µV/m) at Nearest point of Finland (P.1546-6, 677.1 km). Score 5 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, neighbouring_administration, calculation_available. Status SCREENED_LOW_PRIORITY.
- **POL FB LID1001** — notice `92817514` (assignment 124021621, GE06L:B), 803.5 MHz / 5000.0 kHz, NEW; 648.35 km from Finland; 3 special-interest overlaps; -34.0 dB(µV/m) at Nearest point of Finland (P.1546-6, 648.4 km). Score 5 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap, finnish_land_mobile_allocation, neighbouring_administration, calculation_available. Status SCREENED_LOW_PRIORITY.

## Neighbouring administrations: activity

ADD and MODIFY notices of neighbouring administrations, by band, station class and bandwidth, against the previous issue when given. Counts only; a change in counts is an observation for an expert, not a finding.

| Administration | Dimension | Value | This issue | Previous |
| --- | --- | --- | ---: | ---: |
| D | band | <30 MHz | 23 | 11 |
| D | bandwidth_khz | 3.0 | 13 | 0 |
| D | bandwidth_khz | 24.0 | 10 | 0 |
| D | class | FX | 23 | 11 |
| D | total | notices | 23 | 11 |
| POL | band | 790-960 MHz | 9 | 0 |
| POL | bandwidth_khz | 5000.0 | 9 | 0 |
| POL | class | FB | 9 | 0 |
| POL | total | notices | 9 | 0 |
| RUS | band | >=3000 MHz | 176 | 375 |
| RUS | band | 88-174 MHz | 81 | 64 |
| RUS | band | 790-960 MHz | 22 | 0 |
| RUS | band | 174-470 MHz | 11 | 17 |
| RUS | bandwidth_khz | 56000.0 | 165 | 300 |
| RUS | bandwidth_khz | 11.0 | 53 | 8 |
| RUS | bandwidth_khz | 16.8 | 28 | 13 |
| RUS | bandwidth_khz | 5000.0 | 12 | 0 |
| RUS | bandwidth_khz | 7200.0 | 10 | 0 |
| RUS | bandwidth_khz | 18.0 | 7 | 9 |
| RUS | bandwidth_khz | 28000.0 | 7 | 27 |
| RUS | bandwidth_khz | 16.0 | 4 | 23 |
| RUS | bandwidth_khz | 20000.0 | 2 | 10 |
| RUS | bandwidth_khz | 112000.0 | 2 | 9 |
| RUS | class | FX | 176 | 365 |
| RUS | class | ML | 62 | 46 |
| RUS | class | FB | 52 | 44 |
| RUS | total | notices | 290 | 478 |

## Limitations

- Terrestrial criterion: ECC T/R 25-08 A1.2.3 coordination thresholds (normative 29.7-470 MHz; above 470 MHz a challenge extension). Bandwidth correction assumes a uniform spectral power distribution. The 1 % time variant for digital systems (footnote 2) is not applied. No 10 m to 3 m receiving-height correction (organizers: not required).
- Boundaries: Natural Earth 1:10m land borders and the Traficom territorial-sea limit (WFS); screening geometry, not legal boundaries. The territorial-sea layer ends near 65.5 N in the Bay of Bothnia.
- Space: no approved PFD criterion; RR Article 21 Table 21-4 values must be entered from the authoritative edition before comparison.
- Special-interest stations are synthetic challenge data.
- Terrestrial: no terrain database (heff = ha, no clearance-angle correction); antenna patterns are not applied, so values are for the direction of maximum radiation.
- Space: PFD values are upper bounds, not predictions; antenna patterns, pointing, power control and EPFD aggregation are not modelled.
- Space field meanings follow the SNS v9.1 data dictionary; ITU publishes no v10 dictionary.
