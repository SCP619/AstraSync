# Processing pipeline

The same code runs in two places: the platform (worker jobs, results in the UI and API) and the
command line (`ific_evaluate`, which produced the files in this package).

```
ITU index pages ─▶ discover ─▶ download (HTTPS, allow-listed host, no redirects, size limit)
   ─▶ SHA-256, immutable original, revision ─▶ quarantine or accept
   ─▶ parse in an isolated process (itu_ific) ─▶ records (raw + normalized + quality findings)
   ─▶ RELEVANCE job / ific_evaluate:
        change detection ─▶ A frequency ─▶ B service ─▶ C geography / orbit
        ─▶ D calculations (P.1546-6 border screening │ space PFD upper bound)
        ─▶ criterion and concern class (terrestrial) ─▶ E priority
   ─▶ findings (SHA-256 stored) ─▶ cases for HIGH items ─▶ analysis runs ─▶ grounded drafts
   ─▶ expert review ─▶ evidence export
```

| Stage | Space | Terrestrial |
| --- | --- | --- |
| Supported inputs | `ific<N>.zip` / `.mdb` (SNS v10) | `brific<N>.zip` / `.mdb` (MDB extract) |
| Validation | One safe `.mdb` member, ≤ 4 GiB, compression ratio ≤ 200, issue number from the database, implausible power values excluded and reported | Same archive rules; issue from `pub_current_circ`; reconciliation with the ITU ReadMe per part |
| Normalization | Units from the SNS dictionary; raw text kept; missing stays missing | Units from the Preface; e.i.r.p. → e.r.p. −2.15 dB; missing stays missing |
| Filtering | All notices of the issue | Land-mobile classes FB, ML, FL |
| Frequency matching | Groups vs M4 sub-bands and workbook TX/RX intervals (closed intervals) | Same, per notice |
| Calculation | Free-space PFD, peak gain, minimum slant range over the Finland grid | P.1546-6 at Finnish land-border and territorial-sea samples (and at matched workbook stations, indicative) |
| Regulatory screening | Not applied (no approved Table 21-4) | ECC T/R 25-08 A1.2.3 threshold, bandwidth correction, margin |
| Classification | Status + priority tier | Concern class + priority tier |
| Output | CSV, XLSX, JSON, Markdown | CSV, XLSX, JSON, Markdown, border points |

Platform API (all require sign-in and server-side permissions): `GET /api/v1/ific/analyses`,
`GET /api/v1/ific/analyses/{id}/findings`, case endpoints (`/api/v1/cases/...`: analysis, drafts,
reviews, questions, export), source check `POST /api/v1/admin/sources/{id}/check`.

Command line: see [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

Limits that apply to every run: [`../06_Technical_Documentation/LIMITATIONS.md`](../06_Technical_Documentation/LIMITATIONS.md).
