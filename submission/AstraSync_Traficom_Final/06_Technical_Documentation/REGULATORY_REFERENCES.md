# Regulatory references and how they are used

| Reference | Use in AstraSync | Status |
| --- | --- | --- |
| ITU Radio Regulations, Article 21, Table 21-4 (PFD limits for space stations, protecting terrestrial services) | Primary reference for space PFD per the organizers (C10). **Not applied**: the complete authoritative table was not obtained (only WRC-23 amendments in the Final Acts), and the −152 dB(W/m²)/4 kHz example is not used as a constant. Space results carry `regulatory_finding = NOT_EVALUATED` | Blocked |
| RR Nos. 1.161–1.163 (e.i.r.p., e.r.p., e.m.r.p.) | Power type of terrestrial notices; e.i.r.p. → e.r.p. −2.15 dB | Applied |
| RR Appendix 4 / SNS data items v9.1 | Meaning of Space IFIC fields | Applied (field definitions) |
| BR IFIC Preface (Terrestrial Services) | Meaning, units and codes of terrestrial fields; land-mobile station classes FB, ML, FL | Applied |
| ITU-R P.1546-6 | Terrestrial field-strength prediction, 30–4000 MHz, ≤ 1000 km | Applied; port validated against the WP 3K reference |
| ITU-R P.525 | Free-space context of the space PFD upper bound | Applied |
| ECC Recommendation T/R 25-08, Edition 6 June 2025, Annex 1 A1.2.3 (docdb.cept.org/download/4789) | Indicative coordination thresholds 0/6/12/18/20 dB(µV/m) for 29.7–47 / 47–108 / 108–380 / 380–400 / 400–470 MHz at the border line, 10 m, 50 % locations, 10 % time, 25 kHz; footnote 2 (1 % time for digital in certain situations) recorded, not applied | Applied |
| Organizer extension of T/R 25-08 above 470 MHz (C14) | 20 dB(µV/m) up to 4000 MHz, labelled `CHALLENGE_EXTENSION_ABOVE_470_MHZ` | Applied, challenge-specific |
| Traficom Regulation M4 (table of frequencies in Finland), open-data API v13 | Finnish allocations and services in each band (stages A/B) | Applied (snapshot; the API does not name its M4 edition) |
| Traficom Regulation M15 (licence-exempt devices) | Context only; not machine-ingested | Not used in calculations |
| CEPT ECO documentation database | Source of T/R 25-08; harmonisation material not ingested | Partially used |

**Meaning of results.** A terrestrial exceedance of an indicative coordination threshold means
coordination with Finland is indicated under the stated assumptions. It is not harmful
interference, not non-compliance. A frequency overlap alone is only a screening signal. Space PFD
values are upper bounds and are not compared with any limit.

The organizers' clarifications and how each is applied (C1–C24):
`docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md` in the repository.
