# Inputs and outputs

## Input inventory

| Input | Format | Source | Public? | SHA-256 used for the submitted results |
| --- | --- | --- | --- | --- |
| Space IFIC 3074 | ZIP of one SNS v10 MS Access `.mdb` | https://www.itu.int/sns/ific10/ific3074.zip | Yes (ITU, free trial service) | `c8adf75044bca9d6a2be4213d051805f1b0a88d716fb184bcb1cd812216da721` |
| Space IFIC 3073 (comparison) | as above | https://www.itu.int/sns/ific10/ific3073.zip | Yes | `e1bd33e94e4342e6723a898630adac718c8b6406df594cef19a92b4a8b983513` |
| Terrestrial BR IFIC 3076 | ZIP of one `.mdb` (MDB extract) | https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3076.zip | Yes | `ba9d0605a4a5494162e17650c290401d84deaef29030cbdbb61e4b00c834c4c2` |
| Terrestrial BR IFIC 3075 (comparison) | as above | …/MDB/brific3075.zip | Yes | `6f63a3dee548422cc722fd95adf7ce99f13abd8c786459d535c73e3320ed92f7` |
| Finnish table of frequencies (M4) | JSON (OData), API v13 | https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko | Yes, CC BY 4.0 | `41ffdd0ed84a40c19fd4bb3771699a63c879b1ad4f2201dcb1cd3c37524871fb` (snapshot 2026-11-08; the API changes over time) |
| Frequencies of interest | XLSX, sheet "Frequencies of interest" | Challenge platform | No (challenge data, synthetic) | `bb7f481f085fb6c457efc04b9b6bb8250c42ea81bab4b4a0e518c93834e03c8a` |
| ECC T/R 25-08 A1.2.3 thresholds | Entered with citation in `criteria/tr2508_a123.json` | docdb.cept.org/download/4789 | Yes | in the repository |
| Finland boundaries | JSON, derived from Natural Earth (public domain) and Traficom territorial-sea WFS (CC BY 4.0) | in the repository | Yes | in the repository |

Raw inputs are **not** included in this package; the IFIC databases and M4 snapshot can be
downloaded again from the URLs above, and the workbook is the organizers' own file.

## Outputs per issue

| File | Format | Purpose |
| --- | --- | --- |
| `findings.csv` | CSV, one row per notice | The results table (columns: [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)) |
| `*_results.xlsx` | XLSX | Same results with About / Results / (Border points) / Inputs sheets |
| `terrestrial_ific_3076_cases.json` | JSON | Notices above the threshold with full evidence |
| `border_points.csv` | CSV | Top 5 boundary points per terrestrial notice |
| `findings_high.json`, `findings.json.gz` | JSON | Every stage result, calculation input, assumption and hash |
| `comparison.json` | JSON | Change types vs the previous issue; terrestrial trends |
| `manifest.json` | JSON | Input hashes and URLs, parser/rule/method versions, implementation hashes, parameters |
| `report.md` | Markdown | Human-readable report |

Every finding names its source record (`record_key`, e.g. `fxm_terra!93075637` or the `grp` ID),
and every calculation carries its inputs, method version, implementation SHA-256 and a
`calculation_sha256` over inputs and result.

## Worked example: Space

Verified result, `02_Space_IFIC_3074/findings_high.json`, notice `126545119`.

| Step | Value |
| --- | --- |
| Notice | Administration D, SOLAR SENTRY, non-GSO space station, Special Section API/A/14387 → change NEW (API/A without target) |
| Geometry | Inclination 97.4–97.7°, altitude 510–590 km → reaches Finnish latitudes; minimum slant range r = 510 km (lowest perigee, satellite at zenith over 59.7° N) |
| Group | `grp` 126664722, beam TXUHF, transmit, 401.000–401.050 MHz, class/service ET/CV, service area includes FIN; band holds a Finnish terrestrial service (M4) |
| EIRP density (upper bound) | notified maximum power density + maximum beam gain = −40.80 dBW/Hz |
| Spreading | 10·log10(4π·(510 000 m)²) = 125.14 dB(m²) |
| PFD | −40.80 − 125.14 = **−165.94 dB(W/m²) in 1 Hz** (upper bound) |
| Limit, margin | None: no approved RR Article 21 Table 21-4 entry |
| Priority | change +1, special-interest overlap on a downlink +3 (another group, 2244–2246 MHz), service area FIN +3, reaches Finland +2, Finnish terrestrial service +1, API/A +1, PFD available +1 = 12 → HIGH → `EXPERT_REVIEW_REQUIRED` |
| Hashes | implementation `d9e450a0…`, calculation `f9af5f23d34b5cd03915073663928bfdb93e8363143a65928e9128b3528ed4b7` |

## Worked example: Terrestrial

Verified result, `03_Terrestrial_IFIC_3076/terrestrial_ific_3076_cases.json`, notice `93075637`.

| Step | Value |
| --- | --- |
| Notice | `fxm_terra!93075637`, assignment 126074220, RUS, station class FB, KRL LYASKELYA, published NTFD_RR Part II; intent ADD → NEW |
| Frequency | 152.9 MHz, 16.8 kHz; overlaps 4 workbook station intervals (e.g. station 615366 TX, 152.88995–152.89755 MHz) |
| Transmitter | e.r.p. 17.4 dBW as notified (RR 1.162), antenna 26 m above ground, heff = ha = 26 m |
| Border screening | 129 land-border samples within 150 km; maximum at 62.01709 N, 30.38678 E (Finland–Russia land border), 42.55 km, all-land path |
| Propagation | P.1546-6, 10 % time, 50 % locations, receiver 10 m, rural → **E = 20.883 dB(µV/m)** (calculation `41f5a704…`) |
| Criterion | T/R 25-08 A1.2.3, 108–380 MHz band: 12 dB(µV/m); 16.8 kHz ≤ 25 kHz → no bandwidth correction; threshold 12.0 |
| Margin | 20.883 − 12.0 = **+8.88 dB** |
| Class | Finland not named in the coordination rows → `VERIFIED_CRITERION_EXCEEDANCE`: coordination with Finland indicated (not harmful interference, not non-compliance) |
