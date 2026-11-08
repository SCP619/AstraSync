# Reproducing the 3074 and 3076 results

Verified on 2026-11-08: both commands below, run from a clean checkout of commit
`8e0f10535850d604911c430a8dc640ea960c925a` with the inputs of
[`INPUT_OUTPUT_GUIDE.md`](INPUT_OUTPUT_GUIDE.md), reproduced the submitted outputs: `findings.json`
(decompressed), `findings_high.json`, `comparison.json` and `terrestrial_ific_3076_cases.json`
byte-identical; `findings.csv` and `border_points.csv` identical except line endings (the CSV writer
emits CRLF, the repository stores LF). `manifest.json` differs by its `generated_at_utc`; the XLSX workbooks
(built from the same CSV) were not compared byte for byte. Space takes about 3 minutes, terrestrial about 30 seconds.

1. Install the repository ([`../05_Code_Repository/INSTALLATION_GUIDE.md`](../05_Code_Repository/INSTALLATION_GUIDE.md)).
2. Put the inputs in one folder and check them with `Get-FileHash <file> -Algorithm SHA256`
   against `manifest.json`. A newer M4 snapshot can change Finnish allocation matches.
3. From the repository root, with the backend virtual environment:

```powershell
traficom-integration\backend\.venv\Scripts\python -m astrasync_data.ific_evaluate space --issue ific3074.zip --previous ific3073.zip --m4 Taajuusjakotaulukko-v13.json --workbook Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx --out out\space_3074
```

```powershell
traficom-integration\backend\.venv\Scripts\python -m astrasync_data.ific_evaluate terrestrial --issue brific3076.zip --previous brific3075.zip --m4 Taajuusjakotaulukko-v13.json --workbook Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx --out out\terrestrial_3076
```

Other issues: the same command with any `ific<N>.zip` / `brific<N>.zip`; `--previous` is optional.

P.1546-6 validation against the ITU-R WP 3K reference (download https://github.com/eeveetza/p1546):

```powershell
$env:ASTRASYNC_P1546_REFERENCE = "<path>\p1546-main\matlab"; traficom-integration\backend\.venv\Scripts\python -m pytest astrasync-core-lib\tests\test_p1546.py
```

Real-data parser checks (reconciliation of 3076 with the ITU ReadMe, every 3074 notice kept, the
3074 power anomaly):

```powershell
$env:ASTRASYNC_IFIC_DATA = "<folder with the zips>"; traficom-integration\backend\.venv\Scripts\python -m pytest astrasync-core-lib\tests\test_itu_ific.py
```
