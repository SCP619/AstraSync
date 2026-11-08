# Traficom challenge clarifications: decision register

How AstraSync applies the organizers' answers to participant questions (Since AI 2026, "Saving
Earth from Space Interferers Using Radio Frequencies"). Organizer answers are paraphrased from
the participant Q&A as relayed by the team; they are **challenge-specific screening rules**, not
general ITU/CEPT requirements. "Assumption" marks a choice AstraSync made where no answer is
conclusive.

Status values: **Implemented** (code and tests), **Partial**, **Not implemented**, **Blocked**.

| # | Topic | Organizer clarification | AstraSync behaviour | Module / config | Tests | Output field | Conclusive? | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | RX/TX protection | For downlinks, Finnish receiving use is protected; use RX frequencies, and TX frequencies too (Finnish transmissions are received elsewhere in Finland) | Both TX and RX of each workbook station are screening intervals | `ific_analysis.station_references` | `test_ific_analysis.py` | `stage_a_frequency.stations[].reference_key` (`:TX`/`:RX`) | Yes | Implemented |
| C2 | Licence class | Licence class is not the key field; unmapped classes may become MUUT | `licence_class_normalized` = BC, BT, FX, MVV, MUUT, else MUUT; raw value kept; station number always kept | `traficom_workbook._licence_class` | `test_traficom_workbook.py` | `reference_station.licence_class_normalized` | Yes | Implemented |
| C3 | Bandwidth mismatches | The workbook has transcription errors; use the smaller value where channel and transmission bandwidth disagree | Raw widths kept; `effective_bandwidth_hz` = smaller valid value if they differ by more than 1 %; `BANDWIDTH_MISMATCH` quality finding; screening intervals use the effective width | `traficom_workbook._effective_bandwidth`, `BANDWIDTH_MISMATCH_TOLERANCE` | `test_traficom_workbook.py` | `effective_bandwidth_hz`, `effective_bandwidth_rule` | Yes | Implemented |
| C4 | Station 440557 | 2500 kHz channel vs `118600k` transmission is a copy/paste error | Screens at 2.5 MHz. In the real workbook 8 rows share this pattern (17 mismatches in total of 874 rows) | as C3 | `test_station_440557_style_mismatch...` | as C3 | Yes | Implemented |
| C5 | BC 9 / 10 kHz | 9 kHz is the European broadcast channel; 10 kHz also acceptable if consistent | 9 kHz (smaller-value rule); 9 BC rows affected | as C3 | `test_broadcast_9_and_10_khz...` | as C3 | Yes | Implemented |
| C6 | Broadcasting coverage | Assess the receiving coverage area, not only the transmitter site | Space: the PFD upper bound is taken at the worst node of a grid over all of Finland (C8), so every receiving location in Finland, including any broadcast coverage area, is covered conservatively. Terrestrial: no coverage contour is computed, because that needs an approved minimum usable field strength per service, which is not given | `geo.finland_grid`, `ific_analysis._space_geometry` | `test_gso_geometry_reports_the_grid...` | `stage_c_geometry.evaluation_grid` | Yes | Partial (space covered by the grid) |
| C7 | Fixed-service receivers | The FX transmitter site is not necessarily the receiver | FX rows are not used as receiver locations for border criteria; no receiver geometry invented | — | — | — | Yes | Partial (documented only) |
| C8 | Finland grid | An evaluation grid over Finland is acceptable | GSO geometry over 500 grid nodes inside the Natural Earth Finland outline (0.25° lat × 0.5° lon, about 28 km; WGS-84 degrees); minimum slant range, its location and elevation, elevation range across Finland. NGSO still uses the latitude range | `geo.finland_grid`, `GRID_STEP_*` | `test_the_finland_grid_covers_the_country...` | `stage_c_geometry.evaluation_grid` | Yes | Implemented (GSO) |
| C9 | Worst-case beam | Assume peak satellite gain toward Finland when pointing is unknown (GSO, non-GSO, steerable) | Space PFD is a free-space upper bound with peak gain; labelled upper bound, not EPFD | `astrasync_physics.space_pfd` | `test_space_pfd.py` | `max_pfd`, `assumptions` | Yes | Implemented |
| C10 | RR PFD limits | RR Article 21 Table 21-4 is the primary reference | No limit entered: the complete authoritative Table 21-4 was not obtained (only WRC-23 amendments in the Final Acts). The −152 dB(W/m²)/4 kHz example is **not** used as a constant | `criteria.py` registry | — | `regulatory_finding` | Yes (source) | Blocked |
| C11 | Finnish GSO filings | ITU Space Explorer lists Finnish GSO filings; a filing is not a plan position | Not ingested; no plan positions invented | — | — | — | Yes | Not implemented |
| C12 | Land-mobile scope / P.1546-6 | Land-mobile notices only; P.1546-6 at 10 % time, land/rural, no terrain is acceptable | Only `is_land_mobile` notices: station classes FB, ML, FL (`itu_ific.LAND_MOBILE_CLASSES`, per the BR IFIC Preface); the participants' wider list (LR, AL, AM) is not treated as authoritative; FX is excluded; P.1546-6 port validated on 54 reference cases; heff = ha | `ific_analysis.analyse_terrestrial`, `astrasync_physics.p1546` | `test_p1546.py`, `test_ific_analysis.py` | `calculations`, `border_screening.parameters` | Yes | Implemented |
| C13 | Criterion | ECC T/R 25-08 A1.2.3 general land-mobile thresholds | Values read from the 6 June 2025 edition (docdb.cept.org/download/4789): 0 / 6 / 12 / 18 / 20 dB(µV/m) for 29.7–47 / 47–108 / 108–380 / 380–400 / 400–470 MHz; co-channel, 50 % locations, 10 % time, 10 m, 25 kHz, at the border line; BC = 10 log10(spacing / 25 kHz) for wider channels (uniform PSD assumed) | `criteria/tr2508_a123.json`, `border_screening.threshold` | `test_border_screening.py` | `criterion.*` | Yes | Implemented |
| C14 | Above 470 MHz | The above-400 MHz criterion may be applied above 470 MHz | 20 dB(µV/m) up to 4000 MHz (P.1546 range), labelled `CHALLENGE_EXTENSION_ABOVE_470_MHZ`, switchable in the JSON | as C13 | `test_thresholds_follow_the_cited_table` | `criterion.basis` | Yes | Implemented |
| C15 | Digital systems | No general separate time percentage | 10 % time; footnote 2 (1 % for digital in certain situations) recorded, not applied | as C13 | — | `criterion_set.time_percentage_note` | Assumption | Implemented |
| C16 | 10 m → 3 m correction | Not required | Not applied; 10 m receiving height | `ific_analysis.SCREEN_RX_HEIGHT_M` | — | `border_screening.parameters` | Yes | Implemented |
| C17 | Land borders | Evaluate along Finland's land borders | Natural Earth 1:10m FIN vertices shared with RUS, NOR, SWE; resampled every 5 km; every sample within 150 km of the nearest one is evaluated; maximum kept, top 5 exported | `border_screening`, `finland_screening_boundaries.json`, `tools/build_screening_boundaries.py` | `test_border_screening.py` | `border_screening.max_point`, `border_points.csv` | Yes | Implemented |
| C18 | Territorial sea | Also evaluate at the outer limit of the territorial sea (not the coastline); any credible documented dataset | Traficom "Aluevesien rajat" WFS layer `TerritorialSeaArea_L` (CC BY 4.0), EPSG:4326; ends near 65.5 N in the Bay of Bothnia | as C17 | as C17 | `boundary_kind` | Yes | Implemented |
| C19 | Finnish station exposure | Identify exposed workbook stations | P.1546 at up to 10 frequency-matched workbook stations per notice (existing `calculations`); no border criterion applied to them (service-specific criteria unknown), so indicative only | `ific_analysis._terrestrial_finding` | `test_ific_analysis.py` | `calculations[].receiver` | Partial | Partial |
| C20 | Coordination status | A calculated exceedance remains a case even if coordination with Finland appears complete | Coordination rows kept; an exceedance where Finland is named becomes `COORDINATION_REVIEW` (expert review), never "compliant" | `border_screening.coordination_summary`, `classify` | `test_classification_and_coordination` | `coordination`, `concern` | Yes | Implemented |
| C21 | Concern margins | Exceedance is a concern; near-threshold may be; teams choose documented margins; no band has priority | Classes `VERIFIED_CRITERION_EXCEEDANCE`, `COORDINATION_REVIEW`, `POTENTIAL_CONCERN` (within 6 dB, configurable), `BELOW_SCREENING_THRESHOLD`, `FREQUENCY_OVERLAP_ONLY`, `INSUFFICIENT_EVIDENCE`; no band weighting | `border_screening.DEFAULT_CONCERN_MARGIN_DB` | `test_the_concern_margin_is_configurable` | `concern.*` | Yes (team choice allowed) | Implemented |
| C22 | Formats | Separate 3074 and 3076 artifacts; XLSX/CSV/DOC/PDF preferred, JSON acceptable, MDB not needed | `evaluation/space_3074/`, `evaluation/terrestrial_3076/`: CSV, JSON, Markdown report | `ific_evaluate.write_xlsx` | `test_ific_evaluate_xlsx.py` | — | Yes | Implemented: CSV, XLSX, JSON, Markdown (no PDF) |
| C23 | Judging | Weights 25/25/20/15/15 | Priorities followed: criterion and border screening first | — | — | — | Yes | — |
| C24 | BR findings | `A-`, `N-`, `X/21.16` must be read from authoritative definitions | Kept raw; not interpreted | `itu_ific` | — | raw fields | Yes | Implemented (raw only) |

## Meaning of a terrestrial "exceedance"

T/R 25-08 A1.2.3 thresholds are *indicative coordination thresholds* that "should not be
exceeded without coordination between neighbouring countries". A
`VERIFIED_CRITERION_EXCEEDANCE` means: with complete notice inputs and the stated screening
assumptions (no terrain, heff = ha, maximum-radiation direction, uniform PSD), the predicted
field strength at a Finnish border or territorial-sea sample exceeds the threshold. Coordination
with Finland is therefore indicated. It is **not** harmful interference and **not**
non-compliance.

## Real results (IFIC 3076, run 2026-11-08)

1867 land-mobile notices: 6 above the threshold (1 `VERIFIED_CRITERION_EXCEEDANCE`, 5
`COORDINATION_REVIEW`; all Russian FB stations near 152 MHz, land border), 42 below, 534
frequency overlap only, 1285 insufficient evidence (missing inputs or beyond P.1546 scope).
See `evaluation/terrestrial_3076/`.
