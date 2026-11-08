# Scientific validation

| Component | Validation | Result | Status |
| --- | --- | --- | --- |
| ITU-R P.1546-6 field strength (`p1546.py`) | Line-by-line port of the ITU-R WP 3K reference `P1546FieldStrMixed.m` v16 (Zenodo 10.5281/zenodo.6206015); tabulated curves extracted unchanged; compared with all 54 result logs of the reference's validation set (`tests/test_p1546.py`) | Max deviation 5.1×10⁻⁵ dB, median 2×10⁻⁶ dB | Validated against the reference implementation |
| P.1546 method wrapper (`terrestrial_p1546.py`) | Unit tests: 1 kW scaling by e.r.p., refusal outside 30–4000 MHz, 1–50 % time, > 1000 km, missing heff, mixed land/sea paths | Pass in CI | Tested |
| Free-space PFD (`space_pfd.py`) | Analytic vectors (inverse-square law, P.525 context) | Pass in CI | Formula tested; not a validated regulatory method |
| GSO and NGSO geometry (`geo.py`) | Known look angles (sub-satellite point: 90°, 35,793 km; Helsinki to a GSO due south ≈ 22°), NGSO reach, Finland grid coverage | Pass in CI | Tested |
| Border and territorial-sea screening (`border_screening.py`) | Sampling, thresholds per band, bandwidth correction, classification incl. coordination (`test_border_screening.py`) | Pass in CI | Tested |
| T/R 25-08 thresholds | Values read from the 6 June 2025 edition and entered with citation; tests check them against the cited table | Pass in CI | Source-verified by the team; not approved by Traficom |
| Space IFIC parser | 196/196 notices of 3074 kept; impossible power value detected (real data, opt-in test) | Pass | Real data |
| Terrestrial IFIC parser | 3076 reconciles exactly with ITU's per-part notice counts (real data, opt-in test) | Pass | Real data |
| Reproducibility | Both issues re-run from the baseline commit on 2026-11-08 | Identical results | Verified |

## Assumptions that bound every result

**Terrestrial**
- 10 % time, 50 % locations, 10 m receiver, rural, as in T/R 25-08 A1.2.3.
- No terrain data, so heff = ha.
- Maximum notified e.r.p. toward the receiver; no antenna pattern.
- Uniform spectral power density for the bandwidth correction.
- Land/sea path zones from Natural Earth 1:50m land.
- Spherical Earth for distances, an error of about 0.5 %.

**Space**
- Peak beam gain toward Finland (worst case, organizer clarification C9).
- Minimum slant range over the 500-node Finland grid (GSO) or at the lowest perigee (NGSO).
- Free space with no additional loss; single emitter; result per 1 Hz.
- An upper bound only: no EPFD, no aggregation, no antenna pattern, no time variation.

**Geographic sampling**
- Land border: resampled every 5 km, every sample within 150 km of the nearest one evaluated.
- Territorial-sea outer limit: Traficom data, ending near 65.5° N in the Bay of Bothnia.
- GSO grid: 0.25° × 0.5°.

## Not validated

- No independent check of terrestrial field strengths against measurements or another
  propagation tool on the actual 3076 paths.
- No space reference case from the ITU GIBC or SpaceCom tools was run.
- The priority weights are AstraSync's and have not been agreed with Traficom.
