# Limitations

## Scientific and regulatory

1. **No space PFD limit.** RR Article 21 Table 21-4 was not applied: the complete authoritative
   table was not obtained. Space results have no limit, margin or exceedance class; they are ranked
   screenings with PFD upper bounds.
2. **Space PFD is an upper bound.** It uses peak beam gain toward Finland and the minimum slant
   range. There is no EPFD, aggregation, antenna pattern, pointing or power control. Real PFD is
   lower or equal.
3. **No terrain data for P.1546.** heff = ha and no terrain-clearance correction. Field strengths
   can be over- or under-estimated on hilly paths.
4. **Maximum radiated power.** No antenna pattern is applied, so values are for the direction of
   maximum radiation.
5. **Indicative thresholds.** T/R 25-08 values are indicative coordination thresholds. Above
   470 MHz they rest on the organizer-approved extension. Digital-system time percentages
   (footnote 2) are not applied.
6. **Indicative receiver results.** Field strengths at workbook stations carry no
   service-specific criterion; FX receiver locations are not inferred (C7). Coverage contours for
   broadcasting are not computed (C6).
7. **Insufficient evidence.** 1,285 terrestrial notices could not be calculated at the border:
   missing inputs, more than 1,000 km away, or outside 30–4,000 MHz.
8. **Not interpreted.** Finnish GSO filings (C11) are not ingested. BR findings codes and the space
   `act_code` are kept raw.

## Data

- Special-interest stations are synthetic challenge data.
- M4 comes from a dated snapshot, and the API does not name its M4 edition.
- Terrestrial uses the public MDB extract, not the full BR IFIC DVD. Broadcasting tables are
  counted but not analysed.

## Product and deployment

- **Demo video:** not yet recorded.
- **Judge demo:** not hosted at a public URL.
- **Local AI:** needs n8n and Ollama on the same PC; `qwen3:8b` sometimes misformats citations,
  and those replies are refused.
- **Production:** TLS, encryption at rest, a production identity provider, signed packages, an
  Android push gateway, a threat model and per-tenant quotas are not done.
- **Validation and ranking:** priority weights and relevance rules are not approved by Traficom,
  and accuracy against a ground-truth case list has not been measured.
