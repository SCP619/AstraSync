import type { Schemas } from "../api/client";

export const FINDING_TEXT: Record<Schemas["FindingStatus"], string> = {
  NO_IDENTIFIED_CONCERN: "No concern identified",
  POTENTIAL_CONCERN: "Potential concern",
  POTENTIAL_LIMIT_EXCEEDANCE: "Potential limit exceedance",
  INSUFFICIENT_DATA: "Insufficient data",
  METHOD_DISAGREEMENT: "Method disagreement",
  EXPERT_REVIEW_REQUIRED: "Expert review required",
};

export const REVIEW_TEXT: Record<Schemas["ReviewStatus"], string> = {
  NEW: "New",
  IN_REVIEW: "In review",
  NEEDS_MORE_DATA: "Needs more data",
  ACCEPTED: "Finding accepted",
  REJECTED: "Finding rejected",
  CLOSED: "Closed",
};

export const CHANGE_TEXT: Record<Schemas["ChangeType"], string> = {
  NEW: "New",
  MODIFIED: "Modified",
  WITHDRAWN: "Withdrawn",
  UNCHANGED: "Unchanged",
  UNRESOLVED: "Unresolved",
};

export const APPLICABILITY_TEXT: Record<Schemas["MethodApplicability"], string> = {
  APPLICABLE: "Applicable",
  NOT_APPLICABLE: "Not applicable",
  INSUFFICIENT_DATA: "Insufficient data",
  NOT_IMPLEMENTED: "Not implemented",
};

export const EXECUTION_TEXT: Record<Schemas["MethodExecution"], string> = {
  NOT_RUN: "Not run",
  SUCCEEDED: "Ran",
  FAILED: "Failed",
  SKIPPED: "Skipped",
};

export const METRIC_TEXT: Record<Schemas["MetricKind"], string> = {
  PFD: "Power flux density (PFD)",
  EPFD: "Equivalent PFD (EPFD)",
  FIELD_STRENGTH: "Field strength",
  BASIC_TRANSMISSION_LOSS: "Basic transmission loss",
  RECEIVED_INTERFERENCE_POWER: "Received interference power",
};

export const ACTION_TEXT: Record<Schemas["ReviewAction"], string> = {
  ACCEPT_FINDING: "Accept finding",
  REJECT_FINDING: "Reject finding",
  NEEDS_MORE_DATA: "Needs more data",
  FOLLOW_UP: "Follow up",
  CLOSE_NO_CONCERN: "Close: no concern",
  APPROVE_DRAFT: "Approve draft",
  REJECT_DRAFT: "Reject draft",
  ESCALATE: "Escalate as urgent",
};

export const DRAFT_TYPE_TEXT: Record<Schemas["DraftType"], string> = {
  REQUEST_INFORMATION: "Request for information",
  TECHNICAL_INQUIRY: "Technical inquiry",
  COORDINATION_COMMENT: "Coordination comment",
  DRAFT_OBJECTION: "Possible objection",
};

export const DRAFT_STATUS_TEXT: Record<Schemas["DraftStatus"], string> = {
  DRAFT: "AI draft, not approved",
  EDITED: "Edited draft, not approved",
  APPROVED: "Approved by reviewer",
  REJECTED: "Rejected by reviewer",
};

/** Only a server-verified criterion gets a number. A null margin shows a dash, never zero. */
export function formatMargin(
  value: number | null | undefined,
  status: Schemas["CriterionApplicability"] | null | undefined,
): string {
  if (status !== "VERIFIED" || value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)} dB`;
}

export function formatFrequencyRange(start: number, end: number): string {
  return start === end ? `${start} MHz` : `${start}–${end} MHz`;
}

export function formatResult(run: Schemas["MethodRun"]): string {
  if (run.execution_status !== "SUCCEEDED" || run.numeric_value === null) {
    return "Not computed";
  }
  return `${run.numeric_value} ${run.unit ?? ""}`.trim();
}
