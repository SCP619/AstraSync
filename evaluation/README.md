# Evaluation outputs: Space IFIC 3074 and Terrestrial IFIC 3076

Separate outputs for the two issues the challenge evaluates. Both come from the official ITU
downloads, the live Traficom M4 table and the challenge workbook, processed by the same code the
platform runs (`astrasync_data.ific_evaluate`). Method and rules:
[`docs/architecture/IFIC_PIPELINE.md`](../docs/architecture/IFIC_PIPELINE.md).

| Folder | Issue | Compared with | Files |
| --- | --- | --- | --- |
| [`space_3074/`](space_3074/report.md) | Space IFIC 3074 (published 23.06.2026) | 3073 | `report.md`, `findings.csv`, `findings_high.json`, `findings.json.gz`, `comparison.json`, `manifest.json` |
| [`terrestrial_3076/`](terrestrial_3076/report.md) | Terrestrial BR IFIC 3076 (21.07.2026) | 3075 | same, plus `border_points.csv`, `terrestrial_ific_3076_cases.json` and neighbouring-administration trends in `comparison.json` |

- `report.md`: what was done, reconciliation, changes, ranked items with their reasons,
  anomalies, limitations.
- `space_ific_3074_results.xlsx` / `terrestrial_ific_3076_results.xlsx`: About (data status,
  criterion, parameters), Results, Border points (terrestrial) and Inputs sheets, built from the
  CSV files of the same run.
- `findings.csv`: one row per notice, ranked (the results table). Terrestrial rows also carry
  the highest land-border / territorial-sea field strength, its location, the ECC T/R 25-08
  A1.2.3 threshold (with bandwidth correction and basis), the margin, the concern class and the
  coordination rows.
- `border_points.csv` (terrestrial): the five strongest boundary points per notice, each with its
  calculation hash, so geographically distinct exposures stay visible.
- `terrestrial_ific_3076_cases.json`: the notices classed `VERIFIED_CRITERION_EXCEEDANCE`,
  `COORDINATION_REVIEW` or `POTENTIAL_CONCERN`, with the cited criterion.
- `findings.json.gz`: every finding with all stage results, calculations, inputs, assumptions
  and traces. `findings_high.json`: the HIGH tier, uncompressed.
- `manifest.json`: input files with SHA-256 and official URLs, parser, rule and method versions
  (with implementation hashes), screening parameters, environment.

Reproduce (inputs are not in git; download them from the URLs in each `manifest.json`):

```bash
python -m astrasync_data.ific_evaluate space --issue ific3074.zip --previous ific3073.zip --m4 Taajuusjakotaulukko-v13.json --workbook Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx --out evaluation/space_3074
```

```bash
python -m astrasync_data.ific_evaluate terrestrial --issue brific3076.zip --previous brific3075.zip --m4 Taajuusjakotaulukko-v13.json --workbook Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx --out evaluation/terrestrial_3076
```

The M4 table changes over time (its ETag is the version); the manifest records the SHA-256 of
the snapshot used.

**Read with care.** Data status: real IFIC data, screening results for expert review.
Terrestrial notices are compared with the indicative coordination thresholds of ECC T/R 25-08
A1.2.3 (above 470 MHz as the organizer-approved challenge extension): an exceedance indicates
coordination with Finland, not harmful interference or non-compliance. Space downlinks are compared with ITU RR Article 21
Table 21-4 (Edition of 2024) using the worst-case PFD upper bound: a positive margin is a
worst-case exceedance needing the real antenna pattern, not non-compliance
(`space_ific_3074_cases.json`). Special-interest stations are synthetic challenge
data. Decisions: [`docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md`](../docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md).
