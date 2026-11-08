# Terrestrial methodology (side quest: land-mobile notices)

Code: `astrasync-core-lib/data/astrasync_data/itu_ific.py` (parser), `ific_analysis.py`
(analysis), `border_screening.py` (border and territorial-sea screening, criterion, classes),
`astrasync-core-lib/physics/astrasync_physics/p1546.py` (propagation),
`criteria/` (T/R 25-08 criterion set). Rule set `ific-finland-relevance/1.0.0`,
screening `border-screening/1.0.0`.

1. **Input.** `brific<N>.zip` (Terrestrial BR IFIC MDB extract). Issue number from
   `pub_current_circ`. Field meanings from the BR IFIC Preface data dictionary (frequency MHz,
   bandwidth kHz, radius km, height m, power dBW; power type I/E/V = e.i.r.p./e.r.p./e.m.r.p.).
2. **Records.** One per `fxm_terra` row: NOTICE rows of the issue plus RECORDED rows they target
   (context only). Location from `fxm_geo`, transmitter from the first TX antenna in `fxm_ant`.
3. **Change.** From the notice's intent: ADD → NEW, MODIFY → MODIFIED (field-level diff against
   the targeted recorded assignment), SUPPRESS/WITHDRAW → WITHDRAWN. Absence is never withdrawal.
4. **Scope.** Land-mobile station classes FB, ML, FL (BR IFIC Preface; organizer clarification
   C12). FX and others excluded.
5. **Stage A/B.** Overlap with M4 sub-bands (MOBILE / LAND MOBILE allocation, same station class in
   Finland) and with workbook stations' TX and RX intervals (C1, C3).
6. **Propagation.** ITU-R P.1546-6, Python port of the ITU-R WP 3K reference implementation
   (54/54 validation cases within 5.1×10⁻⁵ dB). Parameters: 10 % time, 50 % locations, receiver
   10 m, rural, heff = ha (no terrain data; C12), maximum notified e.r.p. (e.i.r.p. − 2.15 dB when
   notified as e.i.r.p.), no antenna pattern, land/sea path zones from Natural Earth. Mobile areas:
   distance from the area's edge.
7. **Border and territorial-sea screening (C17, C18).** Finland's land border with Russia,
   Norway and Sweden (Natural Earth 1:10m) and the outer limit of the territorial sea (Traficom
   "Aluevesien rajat", CC BY 4.0), resampled every 5 km; every sample within 150 km of the nearest
   one is evaluated; the maximum is kept and the top 5 are exported with calculation hashes.
8. **Criterion (C13, C14).** ECC T/R 25-08 A1.2.3 (Edition 6 June 2025, docdb.cept.org/download/4789):
   0 / 6 / 12 / 18 / 20 dB(µV/m) for 29.7–47 / 47–108 / 108–380 / 380–400 / 400–470 MHz,
   co-channel, 50 % locations, 10 % time, 10 m, 25 kHz reference, at the border line. Above
   470 MHz up to 4000 MHz: 20 dB(µV/m) as the organizer-approved challenge extension, labelled
   `CHALLENGE_EXTENSION_ABOVE_470_MHZ`. Bandwidth correction for wider channels:
   BC = 10·log10(B / 25 kHz), assuming uniform spectral power density.
9. **Classification (C20, C21).** margin = E_max − threshold. margin > 0 →
   `VERIFIED_CRITERION_EXCEEDANCE`, or `COORDINATION_REVIEW` if Finland is named in the notice's
   coordination rows; −6 dB < margin ≤ 0 → `POTENTIAL_CONCERN`; lower → `BELOW_SCREENING_THRESHOLD`;
   no calculation → `FREQUENCY_OVERLAP_ONLY` (if frequency match) or `INSUFFICIENT_EVIDENCE`.
10. **Priority** (orders work): change +1, workbook overlap +3 within 300 km (else +1), Finnish
    land-mobile allocation +1, within 100 km +2, within 300 km +1, neighbouring administration +1,
    calculation available +1. HIGH ≥ 7, MEDIUM ≥ 4.
11. **Trends.** ADD/MODIFY counts of neighbouring administrations by band, station class and
    bandwidth vs the previous issue (`comparison.json`).
