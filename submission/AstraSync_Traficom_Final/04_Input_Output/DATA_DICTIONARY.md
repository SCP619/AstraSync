# Data dictionary

## Source fields used

**Space IFIC (SNS v10; meanings from ITU "SNS data items" v9.1)**

| Table.field | Meaning | Unit |
| --- | --- | --- |
| `notice.ntc_id`, `adm`, `ntc_type`, `wic_no`, `prov`, `ntf_occurs`, `tgt_ntc_id`, `f_int_ext`, `act_code` | Notice ID, notifying administration, type (G/N/S/T/R), IFIC number, provision, first/resubmission, target notice, withdrawal flag, action code (kept raw) | — |
| `com_el/geo/non_geo.sat_name`, `geo.long_nom` | Network name, GSO nominal longitude | °E |
| `orbit.inclin_ang`, `apog_km`, `perig_km` | Non-GSO orbital planes | °, km |
| `grp.grp_id`, `emi_rcp`, `beam_name`, `freq_min`, `freq_max`, `bdwdth` | Frequency group, transmit (E) / receive (R), beam, band edges, bandwidth | MHz, kHz |
| `emiss.pwr_ds_max`, `pwr_ds_min`, `pep_max`, `design_emi` | Max/min power density, peak envelope power, emission designation | dBW/Hz, dBW |
| `s_beam.gain` | Maximum beam gain | dBi |
| `srv_cls.stn_cls/nat_srv`, `srv_area.ctry` | Class of station / nature of service, service-area countries | — |
| `pub_ssn.ssn_ref`, `ssn_no` | Special Section (API/A, CR/C, …) | — |

**Terrestrial BR IFIC (meanings from the BR IFIC Preface data dictionary)**

| Table.field | Meaning | Unit |
| --- | --- | --- |
| `fxm_terra.terrakey`, `assgn_id`, `adm`, `intent`, `stage`, `stn_cls`, `notice_typ`, `prov`, `freq_assgn`, `freq_min/max`, `bdwdth`, `emi_cls` | Notice key, assignment ID, administration, ADD/MODIFY/SUPPRESS, NOTICE/RECORDED, station class, notice type, provision, frequencies, bandwidth, emission class | MHz, kHz |
| `fxm_geo.lat_dec`, `long_dec`, `radius`, `site_name`, `ctry` | Site or area centre, area radius | °, km |
| `fxm_ant.pwr_dbw`, `pwr_eiv`, `hgt_agl`, `gain_max`, `gain_type`, `azm_max_e`, `bmwdth` | Radiated power and type (I/E/V), antenna height, gain, azimuth, beamwidth | dBW, m, dB, ° |
| `fxm_target.target`, `action` | Recorded assignment a notice modifies or suppresses | — |
| `fxm_coord.adm`, `coord_st` | Coordination administration and status | — |
| `pub`, `fxm_pub_hist`, `pub_current_circ` | Publication parts, current circular (issue number) | — |

**M4 table (Traficom API v13):** `ID`, `Sub_band_lower_limit__Hz_`, `Sub_band_upper_limit__Hz_`
(band edges), `Services_in_Finland`, `Sub_band_usage`, `Class_of_station`. Text limits are checked
against the Hz values; `Transmitter_power` 0 means unknown.

**Frequencies-of-interest workbook** (English/Finnish headers): station number (Asemanro),
licence class (Lupalaji, normalized to BC/BT/FX/MVV/MUUT, raw kept), longitude/latitude, ground and
mast height, channel bandwidth (Kan.lev.), TX/RX frequency (TX-/RX-taajuus), antenna height
AGL/ASL, gain, class of transmission, transmission bandwidth (Lähetteen leveys), radiation
direction, polarisation, radiation power and unit, transmission line loss, directivity. The
screening interval of each station is TX and RX centre ± half of the **effective bandwidth** (the
smaller of channel and transmission bandwidth when they differ by more than 1 %;
`BANDWIDTH_MISMATCH` finding; organizer clarifications C3–C5).

## Output columns

**Space `findings.csv`:** `rank`, `notice_id`, `administration`, `notice_type`, `satellite`,
`special_sections`, `change` (NEW / MODIFIED / WITHDRAWN / INDETERMINATE), `geometry` (VISIBLE,
NOT_VISIBLE, REACHES_FINLAND_LATITUDES, DOES_NOT_REACH, EARTH_STATION, UNKNOWN), `groups`,
`downlink_groups_on_special_interest_frequencies`, `max_pfd_db_w_m2_hz_upper_bound`
(dB(W/m²) in 1 Hz, upper bound), `priority_score`, `tier` (HIGH/MEDIUM/LOW), `status`
(EXPERT_REVIEW_REQUIRED, SCREENED_LOW_PRIORITY, INSUFFICIENT_DATA, SCREENED_OUT_GEOMETRY).

**Terrestrial `findings.csv`:** `rank`, `notice_id`, `assignment_id`, `administration`,
`station_class`, `site`, `frequency_mhz`, `bandwidth_khz`, `change`, `distance_to_finland_km`,
`special_interest_overlaps`, `max_field_strength_dbuv_m` (highest of all receivers incl. workbook
stations), `border_max_field_strength_dbuv_m`, `border_point_kind` (LAND_BORDER /
TERRITORIAL_SEA), `border_point_label`, `border_point_lat`, `border_point_lon`,
`border_point_distance_km`, `border_points_evaluated`, `criterion_basis`
(NORMATIVE_T/R_25-08_A1.2.3 or CHALLENGE_EXTENSION_ABOVE_470_MHZ), `base_threshold_dbuv_m`,
`bandwidth_correction_db`, `threshold_dbuv_m`, `margin_db`, `concern_classification`,
`coordination_finland_mentioned`, `coordination_rows`, `priority_score`, `tier`, `status`.

**`border_points.csv`:** `notice_id`, `assignment_id`, `rank_at_notice`, `boundary_kind`,
`boundary_label`, `lat`, `lon`, `distance_km`, `field_strength_dbuv_m`, `threshold_dbuv_m`,
`margin_db`, `calculation_sha256`.

Empty cells mean "not available" (never zero).
