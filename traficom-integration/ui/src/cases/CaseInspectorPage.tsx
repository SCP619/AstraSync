import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, type Schemas } from "../api/client";
import { describeError, RequestId, useLoad, useMe, useSession } from "../shared";
import {
  ACTION_TEXT,
  APPLICABILITY_TEXT,
  CHANGE_TEXT,
  DRAFT_STATUS_TEXT,
  DRAFT_TYPE_TEXT,
  EXECUTION_TEXT,
  FINDING_TEXT,
  formatFrequencyRange,
  formatMargin,
  formatResult,
  METRIC_TEXT,
  REVIEW_TEXT,
} from "./labels";
import { ExecutionBadge, FindingBadge, ReviewBadge, SyntheticBadge } from "../components/StatusBadge";

type Case = Schemas["CaseDetail"];
type Run = Schemas["AnalysisRun"];
type MethodRun = Schemas["MethodRun"];
type Check = Schemas["CriterionCheck"];
type Draft = Schemas["Draft"];

const TABS = ["Overview", "Methods", "Criteria", "Evidence", "Draft and review", "Ask"] as const;
type Tab = (typeof TABS)[number];
const FINISHED: Schemas["AnalysisStatus"][] = [
  "READY",
  "BLOCKED_BY_INPUTS",
  "NOT_APPLICABLE",
  "FAILED",
  "VERIFIED_RESULT",
  "INPUT_SUPERSEDED",
];
const POLL_MS = 2000;

function gate(value: boolean | null): string {
  if (value === null) {
    return "Not assessed";
  }
  return value ? "Match" : "No match";
}

function yesNo(value: boolean | null): string {
  if (value === null) {
    return "Not assessed";
  }
  return value ? "Yes" : "No";
}

function GateRow({ name, value }: { name: string; value: boolean | null }) {
  return (
    <>
      <dt>{name}</dt>
      <dd>{gate(value)}</dd>
    </>
  );
}

function nextStep(item: Case): string {
  if (item.latest_analysis_run_id === null) {
    return "No analysis has run yet. Run one to see which methods can apply.";
  }
  if (item.finding_status === "INSUFFICIENT_DATA") {
    return "Required inputs are missing, so there is no numerical conclusion. Check the Methods tab for what is missing.";
  }
  if (item.finding_status === "POTENTIAL_LIMIT_EXCEEDANCE") {
    return "A prediction exceeds a verified criterion. This is not a finding of harmful interference: expert confirmation is required.";
  }
  return "An expert should review the methods and evidence before any decision.";
}

function Overview({ item }: { item: Case }) {
  const { relevance } = item;
  const overlap =
    relevance.overlap_start_mhz !== null && relevance.overlap_end_mhz !== null
      ? formatFrequencyRange(relevance.overlap_start_mhz, relevance.overlap_end_mhz)
      : "Not assessed";
  return (
    <>
      <p className="notice">{nextStep(item)}</p>
      <h3>What changed</h3>
      <dl>
        <dt>Change</dt>
        <dd>{CHANGE_TEXT[item.change_type]}</dd>
        <dt>Source issue</dt>
        <dd><code>{item.source_issue_id}</code></dd>
        <dt>Administration</dt>
        <dd>{item.administration ?? "Not stated"}</dd>
        <dt>Frequency</dt>
        <dd>{formatFrequencyRange(item.frequency_start_mhz, item.frequency_end_mhz)}</dd>
      </dl>
      <h3>Why Finland might be affected</h3>
      <p className="muted small">
        Each check is separate. A frequency match alone does not mean interference.
      </p>
      <dl>
        <GateRow name="Frequency" value={relevance.frequency_match} />
        <dt>Overlap</dt>
        <dd>{overlap}</dd>
        <GateRow name="Service" value={relevance.service_match} />
        <GateRow name="Geometry or coverage" value={relevance.geometry_match} />
        <dt>Technical data ready</dt>
        <dd>{yesNo(relevance.technical_data_ready)}</dd>
        <dt>Criterion available</dt>
        <dd>{yesNo(relevance.criterion_available)}</dd>
      </dl>
      {relevance.reason_codes.length > 0 && (
        <p className="muted small">Reasons: {relevance.reason_codes.join(", ")}</p>
      )}
    </>
  );
}

function MethodTable({ runs, checks }: { runs: MethodRun[]; checks: Check[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Method</th>
            <th scope="col">Status</th>
            <th scope="col">Result</th>
            <th scope="col">Criterion</th>
            <th scope="col">Margin</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const mine = checks.filter((check) => check.method_run_id === run.method_run_id);
            const verified = mine.filter((check) => check.applicable === "VERIFIED");
            const single = verified.length === 1 ? verified[0] : undefined;
            return (
              <tr key={run.method_run_id}>
                <th scope="row">
                  <code>{run.method_id}</code>
                  <span className="muted small block">
                    {run.standard_ref_id ?? "No standard reference"} · version {run.method_version}
                  </span>
                </th>
                <td>
                  <ExecutionBadge status={run.execution_status} />{" "}
                  <span className="muted small">{APPLICABILITY_TEXT[run.applicability]}</span>
                  {run.missing_fields.length > 0 && (
                    <span className="muted small block">Missing: {run.missing_fields.join(", ")}</span>
                  )}
                  {run.reason_codes.length > 0 && run.missing_fields.length === 0 && (
                    <span className="muted small block">{run.reason_codes.join(", ")}</span>
                  )}
                </td>
                <td className="numeric">
                  {formatResult(run)}
                  {run.reference_bandwidth_hz !== null && (
                    <span className="muted small block">in {run.reference_bandwidth_hz} Hz</span>
                  )}
                </td>
                <td>
                  {verified.length > 1
                    ? `${verified.length} verified criteria: see the Criteria tab`
                    : (single?.citation?.section_id ?? (mine.length > 0 ? "Not verified" : "None"))}
                </td>
                <td className="numeric">{formatMargin(single?.margin_db, single?.applicable)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Methods({ run }: { run: Run | null }) {
  if (run === null) {
    return <p className="muted">No analysis has run yet.</p>;
  }
  // Separate tables per metric, so different quantities can never be read as one number.
  const groups = new Map<Schemas["MetricKind"] | "NONE", MethodRun[]>();
  for (const method of run.method_runs) {
    const key = method.metric_kind ?? "NONE";
    groups.set(key, [...(groups.get(key) ?? []), method]);
  }
  return (
    <>
      <p className="muted small">
        Each method is shown on its own, and results are not averaged. Different metrics are
        different quantities.
      </p>
      {[...groups.entries()].map(([metric, runs]) => (
        <section key={metric} aria-label={metric === "NONE" ? "No metric" : METRIC_TEXT[metric]}>
          <h3>{metric === "NONE" ? "External verification" : METRIC_TEXT[metric]}</h3>
          <MethodTable runs={runs} checks={run.criterion_checks} />
        </section>
      ))}
      <h3>Reproducibility</h3>
      <dl>
        <dt>Analysis run</dt>
        <dd><code>{run.analysis_run_id}</code></dd>
        <dt>Input snapshot</dt>
        <dd><code>{run.input_snapshot_sha256}</code></dd>
        <dt>Software build</dt>
        <dd><code>{run.software_commit_sha}</code></dd>
        <dt>Method registry</dt>
        <dd><code>{run.method_registry_version}</code></dd>
      </dl>
    </>
  );
}

function Criteria({ run }: { run: Run | null }) {
  if (run === null || run.criterion_checks.length === 0) {
    return (
      <p className="muted">
        No criterion has been checked. A prediction without a verified criterion has no margin and
        makes no claim about a limit.
      </p>
    );
  }
  return (
    <ul className="plain">
      {run.criterion_checks.map((check) => (
        <li key={check.criterion_check_id}>
          <strong>{check.citation?.section_id ?? check.criterion_ref_id ?? "Unverified criterion"}</strong>{" "}
          <span className="badge">{check.applicable}</span>
          <dl>
            <dt>Method</dt>
            <dd><code>{check.method_run_id.split("-").pop()}</code></dd>
            <dt>Limit</dt>
            <dd>{check.limit_value === null ? "—" : `${check.limit_value} ${check.limit_unit ?? ""}`}</dd>
            <dt>Comparison</dt>
            <dd>{check.comparison_status}</dd>
            <dt>Margin</dt>
            <dd className="numeric">{formatMargin(check.margin_db, check.applicable)}</dd>
            {check.citation !== null && (
              <>
                <dt>Source</dt>
                <dd className="break">{check.citation.source_url}</dd>
              </>
            )}
          </dl>
          {check.review_note !== null && <p className="muted small">{check.review_note}</p>}
        </li>
      ))}
    </ul>
  );
}

function EvidenceDownload({ evidence }: { evidence: Case["evidence"][number] }) {
  const { api } = useSession();
  const { capabilities } = useMe();
  const [state, setState] = useState<"IDLE" | "BUSY" | string>("IDLE");
  const allowed = capabilities.includes("SOURCE_DOWNLOAD");
  const downloadable = evidence.entity_type === "source_record";

  async function download() {
    setState("BUSY");
    try {
      const record = await api.getRecord(evidence.entity_id);
      const artifact = await api.getArtifact(record.location.artifact_id);
      const megabytes = artifact.byte_length / 1e6;
      if (megabytes > 50 && !window.confirm(`This source file is ${megabytes.toFixed(0)} MB. Download it?`)) {
        setState("IDLE");
        return;
      }
      const blob = await api.downloadArtifact(record.location.artifact_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = artifact.filename_original.split(/[\/]/).pop() ?? "evidence-source";
      link.click();
      URL.revokeObjectURL(url);
      setState("IDLE");
    } catch (error) {
      setState(describeError(error));
    }
  }

  const reason = !allowed
    ? "You do not have download permission"
    : !downloadable
      ? "This evidence has no downloadable file"
      : undefined;
  return (
    <>
      <button
        type="button"
        className="ghost"
        disabled={reason !== undefined || state === "BUSY"}
        title={reason}
        aria-describedby={reason ? `why-${evidence.evidence_id}` : undefined}
        onClick={() => void download()}
      >
        {state === "BUSY" ? "Downloading…" : "Download source file"}
      </button>
      {reason && <span id={`why-${evidence.evidence_id}`} className="sr-only">{reason}</span>}
      {state !== "IDLE" && state !== "BUSY" && <p role="alert">{state}</p>}
    </>
  );
}

function Evidence({ item }: { item: Case }) {
  if (item.evidence.length === 0) {
    return <p className="muted">No evidence is linked to this case yet.</p>;
  }
  return (
    <ul className="plain">
      {item.evidence.map((evidence) => (
        <li key={evidence.evidence_id}>
          <div className="panel-header">
            <strong>{evidence.label}</strong>
            <EvidenceDownload evidence={evidence} />
          </div>
          <dl className="facts">
            <dt>Location</dt>
            <dd><code>{evidence.source_locator}</code></dd>
            <dt>Record SHA-256</dt>
            <dd><code>{evidence.sha256}</code></dd>
            <dt>Publisher trust</dt>
            <dd>{evidence.verified_at_utc === null ? "Not independently verified" : "Verified"}</dd>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function DraftEditor({
  caseId,
  draft,
  canEdit,
  onChanged,
}: {
  caseId: string;
  draft: Draft;
  canEdit: boolean;
  onChanged: () => void;
}) {
  const { api } = useSession();
  const [text, setText] = useState(draft.content_markdown);
  const [error, setError] = useState<unknown>(null);
  const open = draft.status === "DRAFT" || draft.status === "EDITED";
  const changed = text !== draft.content_markdown;

  async function save() {
    setError(null);
    try {
      await api.updateDraft(caseId, draft.draft_id, text);
      onChanged();
    } catch (failure) {
      setError(failure);
    }
  }

  return (
    <li>
      <p>
        <strong>{DRAFT_TYPE_TEXT[draft.draft_type]}</strong>{" "}
        <span className={draft.status === "APPROVED" ? "badge" : "badge review"}>
          {DRAFT_STATUS_TEXT[draft.status]}
        </span>
      </p>
      {draft.warnings.length > 0 && (
        <ul className="notice warnings">
          {draft.warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}
      <label className="stacked">
        Draft text
        <textarea
          rows={6}
          value={text}
          readOnly={!open || !canEdit}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      <p className="muted small">Cites: {draft.citations.length > 0 ? draft.citations.join(", ") : "nothing"}</p>
      {open && canEdit && (
        <button type="button" disabled={!changed} onClick={() => void save()}>Save edits</button>
      )}
      {error !== null && <p role="alert">{describeError(error)}</p>}
    </li>
  );
}

function ReviewForm({
  item,
  run,
  drafts,
  onChanged,
  saved,
  setSaved,
}: {
  item: Case;
  run: Run | null;
  drafts: Draft[];
  onChanged: () => void;
  // Held by the parent, because recording a decision reloads the lists and remounts this form.
  saved: boolean;
  setSaved: (saved: boolean) => void;
}) {
  const { api } = useSession();
  const [error, setError] = useState<unknown>(null);
  const openDrafts = drafts.filter((draft) => draft.status === "DRAFT" || draft.status === "EDITED");
  const hasVerified = run?.criterion_checks.some((check) => check.applicable === "VERIFIED") ?? false;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const [action, draftId] = String(data.get("decision")).split("|") as [
      Schemas["ReviewAction"],
      string | undefined,
    ];
    setError(null);
    setSaved(false);
    try {
      await api.createReview(item.case_id, {
        action,
        decision_reason: String(data.get("reason")),
        analysis_run_id: item.latest_analysis_run_id,
        draft_id: draftId ?? null,
      });
      form.reset();
      setSaved(true);
      onChanged();
    } catch (failure) {
      setError(failure);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="stack">
      <label className="stacked">
        Decision
        <select name="decision" required>
          {(["FOLLOW_UP", "NEEDS_MORE_DATA", "ESCALATE", "ACCEPT_FINDING", "REJECT_FINDING", "CLOSE_NO_CONCERN"] as const)
            .filter((action) => !["ACCEPT_FINDING", "REJECT_FINDING", "CLOSE_NO_CONCERN"].includes(action) || run !== null)
            .map((action) => <option key={action} value={action}>{ACTION_TEXT[action]}</option>)}
          {openDrafts.map((draft) => {
            const blocked = draft.draft_type === "DRAFT_OBJECTION" && !hasVerified;
            return (
              <optgroup key={draft.draft_id} label={DRAFT_TYPE_TEXT[draft.draft_type]}>
                <option value={`APPROVE_DRAFT|${draft.draft_id}`} disabled={blocked}>
                  Approve draft{blocked ? " (needs a verified criterion)" : ""}
                </option>
                <option value={`REJECT_DRAFT|${draft.draft_id}`}>Reject draft</option>
              </optgroup>
            );
          })}
        </select>
      </label>
      <label className="stacked">
        Reason (required, recorded permanently)
        <textarea name="reason" rows={3} required maxLength={4000} />
      </label>
      <button type="submit">Record decision</button>
      {saved && <p role="status">Decision recorded.</p>}
      {error !== null && <p role="alert">{describeError(error)}</p>}
    </form>
  );
}

function DraftAndReview({ item, run }: { item: Case; run: Run | null }) {
  const { api } = useSession();
  const { capabilities } = useMe();
  const [version, setVersion] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) =>
      Promise.all([api.listDrafts(item.case_id, signal), api.listReviews(item.case_id, signal)]),
    // `version` reloads the lists after a change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, item.case_id, version],
  );
  const { result } = useLoad(load);
  const [draftError, setDraftError] = useState<unknown>(null);
  const [creating, setCreating] = useState(false);
  const [decisionSaved, setDecisionSaved] = useState(false);
  const refresh = () => setVersion((value) => value + 1);

  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (run === null) {
      return;
    }
    const type = String(new FormData(event.currentTarget).get("type")) as Schemas["DraftType"];
    setCreating(true);
    setDraftError(null);
    try {
      await api.createDraft(item.case_id, type, run.analysis_run_id);
      refresh();
    } catch (failure) {
      setDraftError(failure);
    } finally {
      setCreating(false);
    }
  }

  if (result === null) {
    return <p role="status">Loading drafts and decisions…</p>;
  }
  if (result.data === undefined) {
    return <p role="alert">{describeError(result.error)}</p>;
  }
  const [drafts, reviews] = result.data;
  const canDraft = capabilities.includes("DRAFT_CREATE");

  return (
    <>
      <h3>Correspondence drafts</h3>
      <p className="muted small">
        AstraSync never sends anything. Drafts need a reviewer's approval and are exported for you
        to use.
      </p>
      {drafts.items.length === 0 && <p className="muted">No drafts yet.</p>}
      <ul className="plain">
        {drafts.items.map((draft) => (
          <DraftEditor
            key={`${draft.draft_id}-${draft.status}`}
            caseId={item.case_id}
            draft={draft}
            canEdit={canDraft}
            onChanged={refresh}
          />
        ))}
      </ul>
      {canDraft && (
        run === null ? (
          <p className="muted">Run an analysis before drafting.</p>
        ) : (
          <form className="inline-form" onSubmit={(event) => void createDraft(event)}>
            <label className="stacked">
              New draft type
              <select name="type">
                {(Object.entries(DRAFT_TYPE_TEXT) as [Schemas["DraftType"], string][]).map(
                  ([value, text]) => <option key={value} value={value}>{text}</option>,
                )}
              </select>
            </label>
            <button type="submit" disabled={creating}>{creating ? "Drafting…" : "Create draft"}</button>
          </form>
        )
      )}
      {draftError !== null && (
        <>
          <p role="alert">{describeError(draftError)}</p>
          {draftError instanceof ApiError && draftError.code === "AI_UNAVAILABLE" && (
            <p className="muted small">Analysis, evidence and review keep working without it.</p>
          )}
        </>
      )}
      <h3>Reviewer decision</h3>
      {capabilities.includes("REVIEW_DECIDE") ? (
        <ReviewForm item={item} run={run} drafts={drafts.items}
          onChanged={refresh}
          saved={decisionSaved}
          setSaved={setDecisionSaved}
        />
      ) : (
        <p className="muted">Only a reviewer can record a decision or approve a draft.</p>
      )}
      <h3>History</h3>
      {reviews.items.length === 0 ? (
        <p className="muted">No decisions recorded.</p>
      ) : (
        <ul className="plain">
          {reviews.items.map((event) => (
            <li key={event.review_event_id}>
              <strong>{ACTION_TEXT[event.action]}</strong>
              <span className="muted small"> · {event.occurred_at_utc.slice(0, 16).replace("T", " ")} UTC</span>
              <br />
              {event.decision_reason}
              <span className="muted small block">By <code>{event.actor_id}</code></span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** Grounded questions: answered only from this case's evidence; the server checks citations. */
export function AskCase({ item, run }: { item: Case; run: Run | null }) {
  const { api } = useSession();
  const { capabilities } = useMe();
  const [answers, setAnswers] = useState<{ question: string; answer: Schemas["CaseAnswer"] }[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [asking, setAsking] = useState(false);

  if (!capabilities.includes("DRAFT_CREATE")) {
    return <p className="muted">Asking the assistant needs the drafting permission.</p>;
  }
  if (run === null) {
    return <p className="muted">Run an analysis first; the assistant answers from its evidence.</p>;
  }
  const runId = run.analysis_run_id;

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const question = String(new FormData(form).get("question") ?? "").trim();
    if (question.length < 3) {
      return;
    }
    setAsking(true);
    setError(null);
    try {
      const answer = await api.askCase(item.case_id, runId, question);
      setAnswers((previous) => [...previous, { question, answer }]);
      form.reset();
    } catch (failure) {
      setError(failure);
    } finally {
      setAsking(false);
    }
  }

  return (
    <>
      <h3>Ask about this case</h3>
      <p className="muted small">
        Answers come from the local model and use only this case's stored evidence. Every answer
        cites its evidence; it is not a finding and needs expert judgement.
      </p>
      <ol className="plain" aria-live="polite">
        {answers.map(({ question, answer }, index) => (
          <li key={index}>
            <p><strong>Q:</strong> {question}</p>
            <p className="pre-wrap"><strong>A:</strong> {answer.answer_markdown}</p>
            <p className="muted small">
              Evidence: {answer.cited_evidence_ids.map((id) => <code key={id}>{id} </code>)}
              {answer.ai_model_id && <> · model {answer.ai_model_id}</>}
            </p>
            {answer.uncertainties.length > 0 && (
              <ul className="small">{answer.uncertainties.map((u) => <li key={u}>{u}</li>)}</ul>
            )}
          </li>
        ))}
      </ol>
      <form className="inline-form" onSubmit={(event) => void ask(event)}>
        <label className="stacked">
          Question
          <textarea name="question" rows={3} maxLength={2000} required minLength={3} />
        </label>
        <button type="submit" disabled={asking}>{asking ? "Asking (this can take minutes)…" : "Ask"}</button>
      </form>
      {error !== null && (
        <>
          <p role="alert">{describeError(error)}</p>
          {error instanceof ApiError && error.code === "AI_UNAVAILABLE" && (
            <p className="muted small">
              The answer was refused or the local model is unavailable. Analysis, evidence and
              review keep working.
            </p>
          )}
        </>
      )}
    </>
  );
}

export function CaseInspectorPage() {
  const { caseId = "" } = useParams();
  const { api } = useSession();
  const { capabilities } = useMe();
  const [version, setVersion] = useState(0);
  const [tab, setTab] = useState<Tab>("Overview");
  const [actionError, setActionError] = useState<unknown>(null);
  const [pendingRun, setPendingRun] = useState<string | null>(null);

  const load = useCallback(
    async (signal: AbortSignal) => {
      const item = await api.getCase(caseId, signal);
      const run = item.latest_analysis_run_id
        ? await api.getAnalysis(item.latest_analysis_run_id, signal)
        : null;
      return { item, run };
    },
    // `version` reloads the case after a change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, caseId, version],
  );
  const { result, retry } = useLoad(load);

  // Reports actual run state. There is no estimated progress to invent.
  useEffect(() => {
    if (pendingRun === null) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      api
        .getAnalysis(pendingRun)
        .then((run) => {
          if (FINISHED.includes(run.analysis_status)) {
            setPendingRun(null);
            setVersion((value) => value + 1);
          }
        })
        .catch((error: unknown) => {
          setPendingRun(null);
          setActionError(error);
        });
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [api, pendingRun]);

  async function analyse() {
    setActionError(null);
    try {
      const accepted = await api.requestAnalysis(caseId);
      setPendingRun(accepted.analysis_run_id);
    } catch (failure) {
      setActionError(failure);
    }
  }

  async function exportPack() {
    setActionError(null);
    try {
      const pack = await api.exportCase(caseId);
      const url = URL.createObjectURL(new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `evidence-pack-${caseId}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (failure) {
      setActionError(failure);
    }
  }

  if (result === null) {
    return <main className="content"><p role="status">Loading case…</p></main>;
  }
  if (result.data === undefined) {
    return (
      <main className="content">
        <p><Link to="/cases">All cases</Link></p>
        <h1>Case unavailable</h1>
        <p role="alert">{describeError(result.error)}</p>
        <RequestId error={result.error} />
        <button type="button" onClick={retry}>Try again</button>
      </main>
    );
  }

  const { item, run } = result.data;
  return (
    <main className="content">
      <p><Link to="/cases">All cases</Link></p>
      <h1>
        {item.notice_id} {item.is_synthetic && <SyntheticBadge label="DEMO / SYNTHETIC" />}
      </h1>
      <p className="muted small break">Case <code>{item.case_id}</code></p>
      <dl className="summary">
        <dt>Finding</dt>
        <dd><FindingBadge status={item.finding_status} /></dd>
        <dt>Review</dt>
        <dd><ReviewBadge status={item.review_status} /></dd>
        <dt>Methods run</dt>
        <dd>{item.method_summary.succeeded} of {item.method_summary.candidates}</dd>
        <dt>Criterion margin</dt>
        <dd className="numeric">{formatMargin(item.margin_db, item.criterion_status)}</dd>
      </dl>
      <div className="actions">
        {capabilities.includes("ANALYSIS_RUN") && (
          <button type="button" disabled={pendingRun !== null} onClick={() => void analyse()}>
            {pendingRun !== null ? "Analysis running…" : run === null ? "Run analysis" : "Run again"}
          </button>
        )}
        {capabilities.includes("CASE_EXPORT") && (
          <button type="button" onClick={() => void exportPack()}>Export evidence pack</button>
        )}
      </div>
      {pendingRun !== null && <p role="status">Analysis queued or running. Results appear when it ends.</p>}
      {actionError !== null && (
        <>
          <p role="alert">{describeError(actionError)}</p>
          <RequestId error={actionError} />
        </>
      )}
      <div role="tablist" aria-label="Case details" className="tabs">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            id={`tab-${name}`}
            aria-selected={tab === name}
            aria-controls="case-panel"
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>
      <section className="panel" role="tabpanel" id="case-panel" aria-labelledby={`tab-${tab}`}>
        {tab === "Overview" && <Overview item={item} />}
        {tab === "Methods" && <Methods run={run} />}
        {tab === "Criteria" && <Criteria run={run} />}
        {tab === "Evidence" && <Evidence item={item} />}
        {tab === "Draft and review" && <DraftAndReview item={item} run={run} />}
        {tab === "Ask" && <AskCase item={item} run={run} />}
      </section>
    </main>
  );
}
