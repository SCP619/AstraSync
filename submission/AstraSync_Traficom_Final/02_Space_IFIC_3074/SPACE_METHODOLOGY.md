# Space methodology

Code: `astrasync-core-lib/data/astrasync_data/itu_ific.py` (parser), `ific_analysis.py`
(analysis), `geo.py` (geometry), `astrasync-core-lib/physics/astrasync_physics/space_pfd.py`
(PFD). Rule set `ific-finland-relevance/1.0.0`.

1. **Input.** `ific<N>.zip` from https://www.itu.int/sns/ific10/: one SNS v10 MS Access database.
   The archive must hold exactly one safely named `.mdb` (size and compression-ratio limits); the
   issue number is read from the notices' `wic_no` and cross-checked with the file name.
2. **Records.** One record per frequency group (`grp`) of each notice in the issue, joined with
   the notice, beam (`s_beam`), emissions (`emiss`), classes of station/service (`srv_cls`),
   service area (`srv_area`), orbit, earth-station location and notified PFD (`c_pfd`). Field
   meanings follow the ITU "SNS data items" v9.1 dictionary (frequencies MHz, bandwidth kHz,
   `pwr_ds_max` dBW/Hz, `pep_max` dBW, gain dBi); originals are kept as text beside them.
3. **Plausibility.** A `pwr_ds_max` above `pep_max` or below `pwr_ds_min` is excluded and reported.
4. **Change.** `f_int_ext` W/Z → WITHDRAWN; `tgt_ntc_id` ≠ own ID → MODIFIED; `ntf_occurs` F or a
   Special Section API/A without target → NEW; otherwise INDETERMINATE. Absence from an issue is
   never a withdrawal. `act_code` is kept raw (its v10 meaning is not documented to us).
5. **Stage A, frequency.** Closed-interval overlap of each group with M4 sub-bands and with the
   workbook stations' TX **and** RX intervals (organizer clarification C1), centre ± half of the
   effective bandwidth (smaller value where channel and transmission widths disagree, C3).
6. **Stage B, service.** Downlink (space-to-Earth) groups in bands where Finland has a terrestrial
   service; service area including FIN.
7. **Stage C, geometry.** GSO: elevation and slant range from a 500-node grid over Finland
   (0.25° × 0.5°, about 28 km, inside the Natural Earth outline; C8); visible if any node sees the
   satellite above 0°. NGSO: whether inclination and altitude let the satellite rise above the
   horizon at 59.7–70.1° N, minimum slant range at the lowest perigee. Earth stations: distance.
8. **Stage D, PFD upper bound.** `PFD = EIRP − 10·log10(4πr²)` (free space, P.525 context) with
   EIRP density = notified maximum power density (dBW/Hz) + **maximum beam gain** (worst case, beam
   peak toward Finland; organizer clarification C9) and r = minimum slant range. Result in
   dB(W/m²) in 1 Hz. Not EPFD, no antenna pattern, no aggregation, no time variation.
9. **Stage E, priority.** Additive, per finding: change NEW/MODIFIED +1, special-interest overlap on
   a downlink +3, service area includes Finland +3, visible/reaches Finland +2, Finnish terrestrial
   service in the band +1, API/A or CR/C +1, AP30/30A/30B +1, PFD available +1. HIGH ≥ 10, MEDIUM
   ≥ 6. Priority orders expert work; it is not a finding.
10. **Regulatory comparison.** None: no approved RR Article 21 Table 21-4 entry (C10). The status
    never exceeds `EXPERT_REVIEW_REQUIRED`; `regulatory_finding` reads `NOT_EVALUATED`.
