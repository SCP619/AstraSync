# AstraSync evaluation: Space IFIC 3074

Publication date (from the database): 2026-06-23. Generated 2026-11-08T07:58:31+00:00 by rule set `ific-finland-relevance/1.0.0`.

**What this is.** A deterministic screening of every notice in the issue against Finnish frequency use (M4 table and the challenge's special-interest stations), with explainable priorities and, where the notice holds the inputs, technical calculations. **Criterion.** Downlink groups are compared with ITU RR Article 21 Table 21-4 (No. 21.16, Edition of 2024, Rev.WRC-23) where band, service (class of station) and orbit condition establish an entry. The PFD is a free-space upper bound with the peak beam gain toward the worst point of a Finland grid (GSO) or the closest pass (NGSO): a negative margin shows the notified maxima stay below the limit; a positive margin is a worst-case exceedance needing the real antenna pattern, never a finding of non-compliance (21.17 also allows agreed exceedance).

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

Notices screened: 196. Priority tiers: {"HIGH": 55, "MEDIUM": 61, "LOW": 80}. Statuses: {"EXPERT_REVIEW_REQUIRED": 55, "SCREENED_LOW_PRIORITY": 63, "INSUFFICIENT_DATA": 33, "SCREENED_OUT_GEOMETRY": 45}.

### Method and assumptions

- Scope: every frequency group of every notice published in this issue.
- A: overlap with special-interest station intervals (M4 overlap recorded). B: downlink in a band where Finland has a terrestrial service; service area FIN. C: GSO elevation from four Finnish points, or NGSO reach of Finnish latitudes. D: PFD inputs present.
- PFD: free-space inverse-square (SPACE_PFD_FREE_SPACE) with an **upper bound** e.i.r.p. density: notified maximum power density + maximum beam gain, as if the beam peak pointed at Finland, at the minimum slant range. Result per 1 Hz.
- Priority score components are listed per finding in `findings.json.gz`; tiers: HIGH ≥ 10, MEDIUM ≥ 6. Priority is for ordering expert work; it is not a statement of concern.

### Highest-priority items

- **D SOLAR SENTRY** — notice `126545119` (NON_GSO_SPACE_STATION, API/A/14387), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -165.9 dB(W/m²) in 1 Hz upper bound. Score 15 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, service_area_includes_finland, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **CHN CSN-SSO** — notice `124545403` (NON_GSO_SPACE_STATION, API/A/13924/M1 API/B/3487), NEW; geometry REACHES_FINLAND_LATITUDES; 55 downlink groups on special-interest frequencies; -112.8 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **E PAZ_2-A** — notice `324520174` (NON_GSO_SPACE_STATION, CR/C/6322 CR/D/5376), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -122.8 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **CHN YG-1** — notice `126545117` (NON_GSO_SPACE_STATION, API/A/14388), NEW; geometry REACHES_FINLAND_LATITUDES; 10 downlink groups on special-interest frequencies; -128.1 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **F F-SAT-NG-15_B** — notice `324520131` (NON_GSO_SPACE_STATION, CR/C/6342 CR/D/5387), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 288 downlink groups on special-interest frequencies; -139.7 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **CHN CHINASAT-G-33.5E** — notice `324520184` (GSO_SPACE_STATION, CR/C/6325 CR/D/5379), MODIFIED; geometry VISIBLE; 10 downlink groups on special-interest frequencies; -147.9 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **CHN CHINASAT-H-60.5E** — notice `324520183` (GSO_SPACE_STATION, CR/C/6324 CR/D/5378), MODIFIED; geometry VISIBLE; 10 downlink groups on special-interest frequencies; -148.0 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **USA USASAT-30-3** — notice `125545390` (NON_GSO_SPACE_STATION, API/A/14228 API/B/3496), NEW; geometry REACHES_FINLAND_LATITUDES; 3 downlink groups on special-interest frequencies; -154.6 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **USA RLNEUTRON-1** — notice `125545347` (NON_GSO_SPACE_STATION, API/A/14223 API/B/3491), NEW; geometry REACHES_FINLAND_LATITUDES; 8 downlink groups on special-interest frequencies; -159.7 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **USA GRAVITAS** — notice `125545368` (NON_GSO_SPACE_STATION, API/A/14225 API/B/3493), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -162.2 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **J AE4LA** — notice `126545060` (NON_GSO_SPACE_STATION, API/A/14331/M1), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -163.4 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **IND INSAT-COM(71E)** — notice `324520214` (GSO_SPACE_STATION, CR/C/6359 CR/D/5372), MODIFIED; geometry VISIBLE; 99 downlink groups on special-interest frequencies; -166.1 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **CHN TIANQI-3E-2** — notice `124545392` (NON_GSO_SPACE_STATION, API/A/13903/M1 API/B/3486), NEW; geometry REACHES_FINLAND_LATITUDES; 3 downlink groups on special-interest frequencies; -168.8 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **F AST-NG-C-4** — notice `317520372` (NON_GSO_SPACE_STATION, CR/C/4587/M6 CR/D/5368), MODIFIED; geometry REACHES_FINLAND_LATITUDES; 4 downlink groups on special-interest frequencies; -172.2 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **E SECOMSAT-5-78E** — notice `324520194` (GSO_SPACE_STATION, CR/C/6344 CR/E/2875), MODIFIED; geometry VISIBLE; 93 downlink groups on special-interest frequencies; -173.7 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **PHL MULA** — notice `125545392` (NON_GSO_SPACE_STATION, API/A/14230 API/B/3498), NEW; geometry REACHES_FINLAND_LATITUDES; 2 downlink groups on special-interest frequencies; -174.9 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **USA SNAPPY** — notice `126545098` (NON_GSO_SPACE_STATION, API/A/14375), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -176.8 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **USA ORACLE-M** — notice `126545148` (NON_GSO_SPACE_STATION, API/A/14383), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -177.4 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **I ION SCV-025** — notice `126545131` (NON_GSO_SPACE_STATION, API/A/14385), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -177.9 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **I ION SCV-026** — notice `126545132` (NON_GSO_SPACE_STATION, API/A/14386), NEW; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -177.9 dB(W/m²) in 1 Hz upper bound. Score 12 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **F AST-NG-C-4** — notice `117520372` (NON_GSO_SPACE_STATION, CR/C/4587/M6 CR/D/5368), INDETERMINATE; geometry REACHES_FINLAND_LATITUDES; 22 downlink groups on special-interest frequencies; -103.6 dB(W/m²) in 1 Hz upper bound. Score 11 (HIGH): special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **RUS RGS-N** — notice `125500066` (NON_GSO_SPACE_STATION, ), NEW; geometry REACHES_FINLAND_LATITUDES; 11 downlink groups on special-interest frequencies; -105.4 dB(W/m²) in 1 Hz upper bound. Score 11 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **CHN GW-S** — notice `125500277` (NON_GSO_SPACE_STATION, ), NEW; geometry REACHES_FINLAND_LATITUDES; 5 downlink groups on special-interest frequencies; -118.8 dB(W/m²) in 1 Hz upper bound. Score 11 (HIGH): change_new_or_modified, special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **E PAZ_2-A** — notice `124520174` (NON_GSO_SPACE_STATION, CR/C/6322 CR/D/5376), INDETERMINATE; geometry REACHES_FINLAND_LATITUDES; 1 downlink groups on special-interest frequencies; -122.8 dB(W/m²) in 1 Hz upper bound. Score 11 (HIGH): special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.
- **F F-SAT-NG-15_B** — notice `124520131` (NON_GSO_SPACE_STATION, CR/C/6342 CR/D/5387), INDETERMINATE; geometry REACHES_FINLAND_LATITUDES; 288 downlink groups on special-interest frequencies; -139.7 dB(W/m²) in 1 Hz upper bound. Score 11 (HIGH): special_interest_frequency_overlap_downlink, visible_from_or_reaches_finland, finnish_terrestrial_service_in_downlink_band, api_a_or_cr_c_special_section, pfd_upper_bound_available, table21_4_worst_case_exceedance. Status EXPERT_REVIEW_REQUIRED.

## Data-quality anomalies in published notices

Values that cannot be right as published (for example a maximum power density above the carrier's peak power). They are excluded from calculations and are candidates for a request for clarification to the notifying administration.

- IND LVI (notice `126545057`), group 126662625, 8M00G2D--: MAX_DENSITY_ABOVE_PEAK_POWER — pwr_ds_max 73.0 dBW/Hz, pwr_ds_min -76.0 dBW/Hz, pep_max -4.0 dBW.

## Limitations

- Terrestrial criterion: ECC T/R 25-08 A1.2.3 coordination thresholds (normative 29.7-470 MHz; above 470 MHz a challenge extension). Bandwidth correction assumes a uniform spectral power distribution. The 1 % time variant for digital systems (footnote 2) is not applied. No 10 m to 3 m receiving-height correction (organizers: not required).
- Boundaries: Natural Earth 1:10m land borders and the Traficom territorial-sea limit (WFS); screening geometry, not legal boundaries. The territorial-sea layer ends near 65.5 N in the Bay of Bothnia.
- Space criterion: RR Table 21-4 entries with country, Region, Resolution or satellite-count conditions that the IFIC data cannot establish are not applied (listed in the manifest). Limits depending on X or Y use the least strict value, so only an exceedance is conclusive there. The 18.6-18.8 GHz aggregate limit (21.16.2) is not modelled. EPFD (Article 22) is not computed.
- Special-interest stations are synthetic challenge data.
- Terrestrial: no terrain database (heff = ha, no clearance-angle correction); antenna patterns are not applied, so values are for the direction of maximum radiation.
- Space: PFD values are upper bounds, not predictions; antenna patterns, pointing, power control and EPFD aggregation are not modelled.
- Space field meanings follow the SNS v9.1 data dictionary; ITU publishes no v10 dictionary.
