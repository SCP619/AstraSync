# Judge demonstration and offline fallback

- Open the UI at `/demo`, or add `?demo=judge` to any address. The sign-in page links to it
  ("View the judge demonstration"), also after a failed sign-in, so it doubles as the offline
  fallback.
- No sign-in, no API calls, no privileges: the page reads only the bundled
  `traficom-integration/ui/src/demo/judge-demo.json`. It cannot reach protected data because it
  has no token and makes no requests (tested in `src/demo/JudgeDemoPage.test.tsx`).
- The dataset is **synthetic**: invented notices (administration `DEMO`, IDs `DEMO-…`) computed by
  the real code (P.1546-6, border and territorial-sea screening against ECC T/R 25-08 A1.2.3, the
  space PFD upper bound on the Finland grid, the workbook parser). Every screen carries a
  "Demonstration data (synthetic)" banner.
- Scenarios: land-border exceedance, territorial-sea exceedance, coordinated notice for review,
  near-threshold (potential concern), below threshold, workbook bandwidth mismatch, space PFD
  upper bound, missing satellite beam data.
- Rebuild (deterministic; same code, same bytes):

  ```bash
  cd astrasync-core-lib
  python tools/build_judge_demo.py --out ../traficom-integration/ui/src/demo/judge-demo.json
  ```

- Static hosting (Vercel, `ui/vercel.json`): `/demo` works without any backend. Everything else
  needs the API and an identity provider reachable from the browser.
