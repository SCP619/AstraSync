# Demo script (3–5 minutes)

Recording status: **pending**. Start state: local stack running with real sources loaded
([`DEMO_ACCESS.md`](DEMO_ACCESS.md)), browser at http://127.0.0.1:5173. Values quoted below are the
verified results in this package; read them off the screen when recording.

| Time | Screen | Action | Say |
| --- | --- | --- | --- |
| 0:00–0:25 | Sign-in | Continue to sign-in → "Analyst, tenant A" | "AstraSync screens ITU IFIC publications for Finland. Access is checked on the server for every request: role, organisation and source rights." |
| 0:25–0:55 | Source library | Show ITU-SPACE-IFIC, ITU-TERRESTRIAL-IFIC, TRAFICOM-M4, CHALLENGE-WORKBOOK | "IFIC databases are downloaded from the ITU website, verified by SHA-256 and kept unchanged. M4 comes from Traficom open data; the frequencies-of-interest workbook from the challenge." |
| 0:55–1:20 | IFIC issues | Point at 3076, 3075, 3074, 3073 rows | "Each new issue is parsed and analysed automatically. 3076 reconciles exactly with the ITU ReadMe notice counts." |
| 1:20–2:30 | `/ific` → 3076, HIGH | Open KRL LYASKELYA (152.9 MHz) | "A new Russian base station 43 km from Finland. P.1546-6 gives 20.9 dB(µV/m) at the Finland–Russia land border. The ECC T/R 25-08 threshold for 108–380 MHz is 12 dB(µV/m), so the margin is +8.9 dB: coordination with Finland is indicated. That is a screening result, not harmful interference. Assumptions are listed: 10 % time, 50 % locations, 10 m receiver, no terrain." |
| 2:30–2:50 | Same issue | Open KRL KOSTOMUKSHA (+14.8 dB) | "Here Finland is already named in the coordination data, so the case goes to coordination review rather than being treated as settled." |
| 2:50–3:30 | `/ific` → 3074 | Open SOLAR SENTRY, then the data-quality anomaly | "Space: all 196 notices of 3074. This new NGSO system's service area includes Finland. The PFD shown is an upper bound with peak beam gain toward Finland, not EPFD, and no Article 21 limit is applied, so there is no margin. AstraSync also flags impossible published values, like +73 dBW/Hz here." |
| 3:30–4:20 | Cases → a 3076 case | Methods and Criteria tabs; Ask: "Why was this case opened?" | "The local model runs through n8n on Ollama on this PC; the answer must cite the case evidence and use only its numbers, or it is refused." |
| 4:20–4:50 | Case → Draft and review; evaluation folder | Create a draft; show `03_Terrestrial_IFIC_3076/findings.csv` | "Drafts need expert approval and are never sent automatically. The full results per issue are exported as CSV, XLSX and JSON." |

Fallback without a backend: open `/demo` and walk the same story on the synthetic scenarios,
stating that the data is synthetic.
