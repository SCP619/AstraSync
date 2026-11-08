# Evaluation outputs: Space IFIC 3074 and Terrestrial IFIC 3076

Separate outputs for the two issues the challenge evaluates. Both come from the official ITU
downloads, the live Traficom M4 table and the challenge workbook, processed by the same code the
platform runs (`astrasync_data.ific_evaluate`). Method and rules:
[`docs/architecture/IFIC_PIPELINE.md`](../docs/architecture/IFIC_PIPELINE.md).

| Folder | Issue | Compared with | Files |
| --- | --- | --- | --- |
| [`space_3074/`](space_3074/report.md) | Space IFIC 3074 (published 23.06.2026) | 3073 | `report.md`, `findings.csv`, `findings_high.json`, `findings.json.gz`, `comparison.json`, `manifest.json` |
| [`terrestrial_3076/`](terrestrial_3076/report.md) | Terrestrial BR IFIC 3076 (21.07.2026) | 3075 | same, plus neighbouring-administration trends in `comparison.json` |

- `report.md`: what was done, reconciliation, changes, ranked items with their reasons,
  anomalies, limitations.
- `findings.csv`: one row per notice, ranked.
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

**Read with care.** No regulatory criterion has been approved, so these are screening results
ranked for expert review, not findings of interference or limit exceedance. Space PFD values are
upper bounds. Special-interest stations are synthetic challenge data.
