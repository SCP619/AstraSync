// Compile-time contract checks, run by `npm run contract:typecheck`. Each @ts-expect-error fails
// the build if the generated types ever start accepting what the backend rejects.
import type { components, paths } from "../schema.gen";

type Schemas = components["schemas"];

// Findings use the closed vocabulary, which has no "confirmed violation" state.
export const allowedFinding: Schemas["FindingStatus"] = "POTENTIAL_LIMIT_EXCEEDANCE";
// @ts-expect-error not a contract finding status
export const inventedFinding: Schemas["FindingStatus"] = "CONFIRMED_VIOLATION";

// A missing margin is null, never a string or an absent field.
export const nullMargin: Schemas["CaseSummary"]["margin_db"] = null;
// @ts-expect-error margin is numeric
export const stringMargin: Schemas["CaseSummary"]["margin_db"] = "2.3";

// PFD and EPFD are distinct metric kinds; generic labels do not exist.
export const epfd: Schemas["MetricKind"] = "EPFD";
// @ts-expect-error not a contract metric kind
export const inventedMetric: Schemas["MetricKind"] = "AVERAGE_PFD";

// Clients cannot send tenant or role claims.
export const forgedUpload = {
  source_type: "SPACE_IFIC",
  usage_classification: "RESTRICTED",
  filename_original: "demo.iso",
  expected_size_bytes: 1,
  // @ts-expect-error tenant is resolved from the validated identity
  tenant_id: "OTHER",
} satisfies Schemas["UploadCreateRequest"];

// A push payload has no field for restricted content.
export const leakyPush = {
  alert_id: "DEMO-ALERT-001",
  category: "CASE_UPDATE",
  created_at_utc: "2026-11-07T12:00:00Z",
  // @ts-expect-error details are fetched after re-authorization
  safe_preview: "Station detail",
} satisfies Schemas["PushPayload"];

// Drafts always require human review.
// @ts-expect-error the contract only allows true
export const unreviewedDraft: Schemas["Draft"]["requires_human_review"] = false;

// Generated operations carry typed parameters and the standard error shape.
type ListCases = paths["/api/v1/cases"]["get"];
export type CasesPage = ListCases["responses"][200]["content"]["application/json"];
export type CaseError = ListCases["responses"][403]["content"]["application/json"];
export const errorCode: CaseError["error"]["code"] = "FORBIDDEN";
export const sort: NonNullable<NonNullable<ListCases["parameters"]["query"]>["sort"]> = "case_id";
