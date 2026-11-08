# Lovable UI prompts (handover)

Status: **prompts only, nothing generated yet.** A prompt is not an implemented UI. Generated
components must be brought into `traficom-integration/ui/src/`, wired to the typed client
(`src/api/client.ts`, types from `src/api/schema.gen.ts`), and pass `npm run contract:check`,
`npm test` and `npm run build` before they count as integrated.

Never paste IFIC records, workbook rows, local configuration or secrets into Lovable. Use the
synthetic examples below or the contract fixtures in `traficom-integration/contract/fixtures/`.

## Shared brief (prepend to every prompt)

> You are building one screen of AstraSync, a professional spectrum-engineering tool for the
> Finnish regulator. Design language: minimal, black and white, high contrast, one accent only
> for state (no decorative colour), system font stack, dense tables with numeric columns
> right-aligned, generous whitespace between sections, no gradients, no illustrations. React 18 +
> TypeScript, function components, no global state library; data comes through props and the
> hooks named below. Every number shows its unit. Never write "violation", "illegal",
> "non-compliant" or "harmful interference": the tool screens; experts decide. Distinguish
> visually and in text: observed source data, calculated values, worst-case assumptions,
> synthetic/demo data. States to implement for every data view: loading (skeleton, `aria-busy`),
> empty (one sentence on why), error (message + "Try again"), forbidden (403: "You do not have
> access to this source"), offline (banner "Offline: showing the last loaded data" or the
> labelled demo dataset). Accessibility: WCAG 2.2 AA, keyboard reachable, visible focus, table
> headers with `scope`, `aria-live="polite"` for async status, no information by colour alone.
> Responsive: ≥1280 px two-pane (list + detail), 768–1279 px stacked with a sticky detail
> header, <768 px single column with tables turned into definition lists. Authorization is
> server-side: hide actions the user's `capabilities` (from `GET /api/v1/me`) do not include,
> but never assume hiding is protection.

## 1. AstraSync Intelligence chat

- Objective: ask about a case or finding; answers are drafted by the backend's grounded agent
  (local Ollama through n8n) and shown with citations.
- Functionality: message list; composer (max 2000 chars); each assistant message lists cited
  evidence IDs `[E:<id>]` rendered as chips that open the Evidence Inspector; an "Unverified"
  badge if the backend marks the answer refused or ungrounded; "Draft for expert review" footer.
- Hierarchy: `ChatPanel` → `MessageList` → `Message` (`role`, `markdown`, `citedEvidenceIds`,
  `status`) → `CitationChip`; `Composer`.
- Props: `caseId: string`; `onOpenEvidence(id: string)`.
- API: today use `POST /api/v1/cases/{case_id}/drafts` (`DraftCreateRequest` → `DraftCreated`)
  and `GET /api/v1/cases/{case_id}/drafts`. A free-form chat endpoint does not exist yet; do not
  invent one in the UI.
- RBAC: composer only with the draft capability; 503 `AI_UNAVAILABLE` → "Local AI is not
  available; deterministic drafting still works".
- Validation: citations clickable; no numbers rendered that are not in the response.

## 2. Raw Data Inspector

- Objective: original source values beside their interpretation for one record.
- Functionality: two columns "As published" / "Interpreted" from `SourceRecordDetail`
  (`raw_fields`, `reference_station`, `quality_findings`, `field_aliases`, `location`); highlight
  `BANDWIDTH_MISMATCH` with raw channel and transmission widths and the `effective_bandwidth_hz`
  and `effective_bandwidth_rule`; `licence_class_code` vs `licence_class_normalized`; link to the
  source location (`GET /api/v1/source-records/{id}/source-location`).
- Props: `sourceRecordId: string`. Hook: `useSourceRecord(id)` wrapping
  `GET /api/v1/source-records/{source_record_id}`.
- RBAC: 403/404 are indistinguishable to the user ("not available").
- Validation: no field silently dropped; nulls shown as "not given", never 0.

## 3. Terrestrial IFIC dashboard and conflict feed

- Objective: rank IFIC 3076 land-mobile findings by concern.
- Functionality: filters by `concern.classification` (`VERIFIED_CRITERION_EXCEEDANCE`,
  `COORDINATION_REVIEW`, `POTENTIAL_CONCERN`, `BELOW_SCREENING_THRESHOLD`,
  `FREQUENCY_OVERLAP_ONLY`, `INSUFFICIENT_EVIDENCE`), administration, change type; columns rank,
  administration, site, frequency (MHz), bandwidth (kHz), border max (dB(µV/m)), threshold,
  margin (dB, signed), boundary kind, coordination-with-Finland flag.
- API: `GET /api/v1/ific/analyses`, `GET /api/v1/ific/analyses/{analysis_id}/findings`
  (`IficFinding.detail` holds `border_screening`, `criterion`, `concern`, `coordination`).
- Detail: reuse the existing `CriterionPanel` (`src/relevance/IficIssuesPage.tsx`).
- Validation: margin sign and units correct; "screening, not a finding" text always visible.

## 4. Geographic screening map

- Objective: show the transmitter, the evaluated Finnish land-border and territorial-sea
  samples, and the maximum point.
- Data: `detail.border_screening.top_points[]` (`lat`, `lon`, `kind`, `field_strength_dbuv_m`),
  `detail.stage_c_geography.nearest_finland_point`, the notice coordinates. Boundary lines: a
  static GeoJSON derived from `astrasync_data/finland_screening_boundaries.json` (public data).
- Library: MapLibre GL with a plain light basemap; no satellite imagery.
- Legend distinguishes land border vs territorial-sea limit, calculated points vs notified site.
- Never draw coordinates that are not in the data.

## 5. Space IFIC dashboard and PFD inspector

- Objective: rank IFIC 3074 notices; show the worst-case PFD upper bound and its inputs.
- Data: `IficFinding` with `domain = SPACE`; `detail.calculations[]` (method `SPACE_PFD_FREE_SPACE`,
  inputs, assumptions, `result_trace`).
- Label every PFD "upper bound (peak gain toward Finland, free space); not EPFD". No limit
  comparison: RR Table 21-4 limits are not configured, so show "No approved criterion".

## 6. P.1546 calculation inspector

- Objective: one calculation's inputs, trace and assumptions.
- Data: a `calculations[]` item or `MethodRun` (`GET /api/v1/analyses/{id}/methods`): frequency,
  distance, e.r.p. basis, heights, time/location %, path zones, `result_trace`, implementation
  hash, validation status (54 WP 3K reference cases).

## 7. Case investigation workspace, evidence and correspondence review

- Data: `GET /api/v1/cases/{id}`, `/analyse`, `/drafts`, `/reviews`, `/export`.
- Layout: left case summary (source notice, protected Finnish use, criterion, margin, concern,
  coordination); centre evidence list; right drafts with review actions (approve/reject with a
  required comment, append-only history). Drafts always carry "requires human review".

## 8. Judge demonstration view (`?demo=judge`)

- Objective: guided tour over a **labelled synthetic** dataset bundled with the UI.
- Must not sign anyone in, add privileges, call protected APIs or show real protected data. A
  persistent banner: "Demonstration data (synthetic). Not live analysis."
- Scenarios: terrestrial border exceedance, territorial-sea exceedance, coordinated notice for
  review, near-threshold case, bandwidth mismatch, missing satellite beam data, space upper bound.

## Integration checklist (per component)

1. Copy only the component files; replace Lovable's data mocks with the hooks above.
2. Types from `schema.gen.ts`; no `any`.
3. Add a Vitest test for loading, empty, error, forbidden states.
4. `npm run contract:check && npm test && npm run build`.
5. Check keyboard navigation and 320 px width.
