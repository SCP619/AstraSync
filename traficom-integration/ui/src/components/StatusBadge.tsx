/**
 * Status badges: always an icon plus words, never colour alone (DBD section 2, TR-UX-003).
 * Adapted from the Lovable prototype (`status.tsx`) to the API's enums. The rose "concern" tone is
 * used only for a potential limit exceedance, which the server sets only with a verified criterion.
 */
import {
  AlertOctagon,
  AlertTriangle,
  Archive,
  CheckCircle2,
  CircleDashed,
  FlaskConical,
  GitCompare,
  HelpCircle,
  Info,
  MinusCircle,
  Pencil,
  Plus,
  ShieldCheck,
  ShieldQuestion,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { Schemas } from "../api/client";
import { CHANGE_TEXT, EXECUTION_TEXT, FINDING_TEXT, REVIEW_TEXT } from "../cases/labels";
import { cn } from "./cn";

export type Tone = "concern" | "review" | "ok" | "neutral" | "info";

const TONE: Record<Tone, string> = {
  concern: "bg-concern-soft text-concern border-concern/40",
  review: "bg-review-soft text-review border-review/40",
  ok: "bg-ok-soft text-ok border-ok/40",
  neutral: "bg-neutral-soft text-neutral border-neutral/40",
  info: "bg-info-soft text-info border-info/40",
};

export function StatusBadge({
  tone,
  icon: Icon,
  label,
  className,
}: {
  tone: Tone;
  icon: LucideIcon;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 py-0.5 text-2xs font-medium",
        TONE[tone],
        className,
      )}
    >
      <Icon className="size-3 shrink-0" aria-hidden />
      {label}
    </span>
  );
}

export function SyntheticBadge({ label = "SYNTHETIC" }: { label?: string }) {
  return <StatusBadge tone="review" icon={FlaskConical} label={label} />;
}

const FINDING: Record<Schemas["FindingStatus"], [Tone, LucideIcon]> = {
  POTENTIAL_LIMIT_EXCEEDANCE: ["concern", AlertOctagon],
  POTENTIAL_CONCERN: ["review", AlertTriangle],
  EXPERT_REVIEW_REQUIRED: ["review", HelpCircle],
  METHOD_DISAGREEMENT: ["review", GitCompare],
  INSUFFICIENT_DATA: ["neutral", CircleDashed],
  NO_IDENTIFIED_CONCERN: ["ok", CheckCircle2],
};

export function FindingBadge({ status }: { status: Schemas["FindingStatus"] }) {
  const [tone, icon] = FINDING[status];
  return <StatusBadge tone={tone} icon={icon} label={FINDING_TEXT[status]} />;
}

const REVIEW: Record<Schemas["ReviewStatus"], [Tone, LucideIcon]> = {
  NEW: ["neutral", CircleDashed],
  IN_REVIEW: ["info", ShieldQuestion],
  NEEDS_MORE_DATA: ["review", Pencil],
  ACCEPTED: ["ok", ShieldCheck],
  REJECTED: ["neutral", XCircle],
  CLOSED: ["neutral", Archive],
};

export function ReviewBadge({ status }: { status: Schemas["ReviewStatus"] }) {
  const [tone, icon] = REVIEW[status];
  return <StatusBadge tone={tone} icon={icon} label={REVIEW_TEXT[status]} />;
}

const CHANGE: Record<Schemas["ChangeType"], [Tone, LucideIcon]> = {
  NEW: ["info", Plus],
  MODIFIED: ["review", Pencil],
  WITHDRAWN: ["neutral", Archive],
  UNCHANGED: ["neutral", MinusCircle],
  UNRESOLVED: ["review", HelpCircle],
};

export function ChangeBadge({ change }: { change: Schemas["ChangeType"] }) {
  const [tone, icon] = CHANGE[change];
  return <StatusBadge tone={tone} icon={icon} label={CHANGE_TEXT[change]} />;
}

const EXECUTION: Record<Schemas["MethodExecution"], [Tone, LucideIcon]> = {
  SUCCEEDED: ["ok", CheckCircle2],
  NOT_RUN: ["neutral", CircleDashed],
  FAILED: ["review", XCircle],
  SKIPPED: ["neutral", MinusCircle],
};

export function ExecutionBadge({ status }: { status: Schemas["MethodExecution"] }) {
  const [tone, icon] = EXECUTION[status];
  return <StatusBadge tone={tone} icon={icon} label={EXECUTION_TEXT[status]} />;
}

const SEVERITY: Record<string, [Tone, LucideIcon]> = {
  BLOCKING: ["review", AlertOctagon],
  WARNING: ["review", AlertTriangle],
  INFO: ["neutral", Info],
};

export function SeverityBadge({ severity }: { severity: string }) {
  const [tone, icon] = SEVERITY[severity] ?? ["neutral", Info];
  return <StatusBadge tone={tone} icon={icon} label={severity} />;
}
