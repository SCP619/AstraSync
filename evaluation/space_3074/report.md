# AstraSync evaluation: Space IFIC 3074

Publication date (from the database): 2026-06-23. Generated 2026-11-08T01:19:39+00:00 by rule set `ific-finland-relevance/1.0.0`.

**What this is.** A deterministic screening of every notice in the issue against Finnish frequency use (M4 table and the challenge's special-interest stations), with explainable priorities and, where the notice holds the inputs, technical calculations. **What it is not.** No approved regulatory criterion is configured, so nothing here is a limit exceedance or a statement of harmful interference. Every high-priority item needs expert review.

## Inputs

| Role | File | Bytes | SHA-256 | Source |
| --- | --- | ---: | --- | --- |
| IFIC issue | `ific3074.zip` | 60837631 | `c8adf75044bca9d6…` | https://www.itu.int/sns/ific10/ific3074.zip |
| previous IFIC issue | `ific3073.zip` | 14113718 | `e1bd33e94e4342e6…` | https://www.itu.int/sns/ific10/ific3073.zip |
| Finnish table of frequencies (M4), Traficom open data, CC BY 4.0 | `Taajuusjakotaulukko-v13.json` | 4359860 | `41ffdd0ed84a40c1…` | https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko |
| Challenge special-interest workbook (synthetic data) | `Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx` | 100809 | `bb7f481f085fb6c4…` | challenge platform |

## Parse and reconciliation

```json
{
 "notices_in_database": 196,
 "notices_in_issue": 196,
 "groups": 34367,
 "notice_type.G": 72,
 "notice_type.N": 112,
 "notice_type.S": 12,
 "special_section.API": 72,
 "special_section.CR": 148,
 "special_section.RES49": 5,
 "records_out": 34367
}
```

## Changes against the previous issue

```json
{
 "issue": 3074,
 "previous_issue": 3073,
 "change_types": {
  "NEW": 96,
  "MODIFIED": 55,
  "INDETERMINATE": 45
 },
 "also_published_in_previous_issue": 0
}
```

NEW, MODIFIED and WITHDRAWN come from the notice itself (terrestrial intent ADD/MODIFY/SUPPRESS; space ntf_occurs, tgt_ntc_id, f_int_ext). An item absent from an issue is never treated as withdrawn: each IFIC carries that issue's notices only.

## Results

Notices screened: 196. Priority tiers: {"HIGH": 1, "MEDIUM": 111, "LOW": 84}. Statuses: {"EXPERT_REVIEW_REQUIRED": 1, "SCREENED_LOW_PRIORITY": 117, "INSUFFICIENT_DATA": 33, "SCREENED_OUT_GEOMETRY": 45}.

### Method and assumptions

- Scope: every frequency group of every notice published in this issue.
- A: overlap with special-interest station intervals (M4 overlap recorded). B: downlink in a band where Finland has a terrestrial service; service area FIN. C: GSO elevation from four Finnish points, or NGSO reach of Finnish latitudes. D: PFD inputs present.
- PFD: free-space inverse-square (SPACE_PFD_FREE_SPACE) with an **upper bound** e.i.r.p. density: notified maximum power density + maximum beam gain, as if the beam peak pointed at Finland, at the minimum slant range. Result per 1 Hz.
- Priority score components are listed per finding in `findings.json.gz`; tiers: HIGH ≥ 10, MEDIUM ≥ 6. Priority is for ordering expert work; it is not a statement of concern.

### Highest-priority items

- **D SOLAR SENTRY** — notice `126545119` (NON_GSO_SPACE_STATION, API/A/14387), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -165.9 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, service_area_includes_finland, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status EXPERT_REVIEW_REQUIRED.
- **CHN CSN-SSO** — notice `124545403` (NON_GSO_SPACE_STATION, API/A/13924/M1 API/B/3487), NEW; geometry REACHES_FINLAND_LATITUDES; 55 downlink groups on special-interest frequencies; -112.8 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **E PAZ_2-A** — notice `324520174` (NON_GSO_SPACE_STATION, CR/C/6322 CR/D/5376), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -122.8 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN GY-2** — notice `125545396` (NON_GSO_SPACE_STATION, API/A/14233 API/B/3501), NEW; geometry REACHES_FINLAND_LATITUDES; 3 downlink groups on special-interest frequencies; -124.7 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN YG-1** — notice `126545117` (NON_GSO_SPACE_STATION, API/A/14388), NEW; geometry REACHES_FINLAND_LATITUDES; 10 downlink groups on special-interest frequencies; -128.1 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN INSIGHT-A** — notice `125545395` (NON_GSO_SPACE_STATION, API/A/14232 API/B/3500), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -130.9 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **KOR LUMIRX-1** — notice `324520203` (NON_GSO_SPACE_STATION, CR/C/6346 CR/D/5364), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -136.1 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN TYSAR-01** — notice `119545232` (NON_GSO_SPACE_STATION, API/A/12472/M1), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -139.6 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **F F-SAT-NG-15_B** — notice `324520131` (NON_GSO_SPACE_STATION, CR/C/6342 CR/D/5387), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 288 downlink groups on special-interest frequencies; -139.7 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN CITYSEC** — notice `125545403` (NON_GSO_SPACE_STATION, API/A/14238 API/B/3506), NEW; geometry REACHES_FINLAND_LATITUDES; 6 downlink groups on special-interest frequencies; -141.3 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN CHINASAT-G-33.5E** — notice `324520184` (GSO_SPACE_STATION, CR/C/6325 CR/D/5379), MODIFIED; geometry VISIBLE; 10 downlink groups on special-interest frequencies; -147.9 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN CHINASAT-H-60.5E** — notice `324520183` (GSO_SPACE_STATION, CR/C/6324 CR/D/5378), MODIFIED; geometry VISIBLE; 10 downlink groups on special-interest frequencies; -148.0 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **USA USASAT-30-3** — notice `125545390` (NON_GSO_SPACE_STATION, API/A/14228 API/B/3496), NEW; geometry REACHES_FINLAND_LATITUDES; 3 downlink groups on special-interest frequencies; -154.6 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **USA RLNEUTRON-1** — notice `125545347` (NON_GSO_SPACE_STATION, API/A/14223 API/B/3491), NEW; geometry REACHES_FINLAND_LATITUDES; 8 downlink groups on special-interest frequencies; -159.7 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **USA GRAVITAS** — notice `125545368` (NON_GSO_SPACE_STATION, API/A/14225 API/B/3493), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -162.2 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **J AE4LA** — notice `126545060` (NON_GSO_SPACE_STATION, API/A/14331/M1), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -163.4 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **IND INSAT-COM(71E)** — notice `324520214` (GSO_SPACE_STATION, CR/C/6359 CR/D/5372), MODIFIED; geometry VISIBLE; 99 downlink groups on special-interest frequencies; -166.1 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **I TYVAK-0404** — notice `125545400` (NON_GSO_SPACE_STATION, API/A/14236 API/B/3504), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -166.2 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **D CLOUDCT** — notice `124545327` (NON_GSO_SPACE_STATION, API/A/13854/M1), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -166.9 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **USA KITASATS** — notice `126545123` (NON_GSO_SPACE_STATION, API/A/14380), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -168.6 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN TIANQI-3E-2** — notice `124545392` (NON_GSO_SPACE_STATION, API/A/13903/M1 API/B/3486), NEW; geometry REACHES_FINLAND_LATITUDES; 3 downlink groups on special-interest frequencies; -168.8 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **KOR K-COMSAT** — notice `126545127` (NON_GSO_SPACE_STATION, API/A/14381), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -171.5 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **F AST-NG-C-4** — notice `317520372` (NON_GSO_SPACE_STATION, CR/C/4587/M6 CR/D/5368), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 4 downlink groups on special-interest frequencies; -172.2 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **CHN GD-B** — notice `126545069` (NON_GSO_SPACE_STATION, API/A/14368), NEW; geometry REACHES_FINLAND_LATITUDES; 3 downlink groups on special-interest frequencies; -172.3 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.
- **E SECOMSAT-5-78E** — notice `324520194` (GSO_SPACE_STATION, CR/C/6344 CR/E/2875), MODIFIED; geometry VISIBLE; 93 downlink groups on special-interest frequencies; -173.7 dB(W/m²) in 1 Hz upper bound. Score 9 (MEDIUM): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available. Status SCREENED_LOW_PRIORITY.

## Data-quality anomalies in published notices

Values that cannot be right as published (for example a maximum power density above the carrier's peak power). They are excluded from calculations and are candidates for a request for clarification to the notifying administration.

- IND LVI (notice `126545057`), group 126662625, 8M00G2D--: MAX_DENSITY_ABOVE_PEAK_POWER — pwr_ds_max 73.0 dBW/Hz, pwr_ds_min -76.0 dBW/Hz, pep_max -4.0 dBW.

## Limitations

- No approved criterion: no margin, no exceedance. Candidate criteria (for example ECC T/R 25-08 trigger field strengths, RR Article 21 PFD limits) must be entered with citations and approved before AstraSync compares against them.
- Special-interest stations are synthetic challenge data.
- Terrestrial: no terrain database (heff = ha, no clearance-angle correction); antenna patterns are not applied, so values are for the direction of maximum radiation.
- Space: PFD values are upper bounds, not predictions; antenna patterns, pointing, power control and EPFD aggregation are not modelled.
- Space field meanings follow the SNS v9.1 data dictionary; ITU publishes no v10 dictionary.
