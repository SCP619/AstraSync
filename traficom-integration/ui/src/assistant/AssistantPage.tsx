/**
 * AstraSync Intelligence: a full page for the grounded assistant. Answers come from the server's
 * grounded agent (local model through n8n) and use only the selected case's stored evidence;
 * the server checks citations and numbers and refuses anything else.
 */
import { useCallback, useState, type FormEvent } from "react";
import { ApiError, type Schemas } from "../api/client";
import { formatFrequencyRange } from "../cases/labels";
import { describeError, useLoad, useMe, useSession } from "../shared";

export const COMMANDS: { label: string; prompt: string }[] = [
  { label: "Summarise this case", prompt: "Summarise this case in three sentences for a spectrum engineer." },
  { label: "Explain the calculation", prompt: "Explain which method was calculated, its inputs and its result." },
  { label: "What is missing?", prompt: "Which inputs or evidence are missing, and what would they change?" },
  { label: "Criterion and margin", prompt: "Explain the applied criterion, the margin and what it means for review." },
  { label: "Coordination context", prompt: "What does the evidence say about coordination with Finland?" },
  { label: "Next review step", prompt: "What should the reviewer check next, based only on the evidence?" },
];

type Turn = { question: string; answer?: Schemas["CaseAnswer"]; error?: unknown };

function caseLabel(item: Schemas["CaseSummary"]): string {
  return `${item.administration ?? "Unknown administration"} · ${formatFrequencyRange(
    item.frequency_start_mhz,
    item.frequency_end_mhz,
  )} · ${item.domain === "SPACE" ? "Space" : "Terrestrial"} notice ${item.notice_id}`;
}

export function AssistantPage() {
  const { api } = useSession();
  const { capabilities } = useMe();
  const loadCases = useCallback(
    (signal: AbortSignal) => api.listCases({ sort: "priority" }, undefined, signal),
    [api],
  );
  const { result: casesResult } = useLoad(loadCases);
  const [caseId, setCaseId] = useState<string>("");
  const [runId, setRunId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const canAsk = capabilities.includes("DRAFT_CREATE");

  async function selectCase(id: string) {
    setCaseId(id);
    setTurns([]);
    setRunId(null);
    if (!id) return;
    try {
      const detail = await api.getCase(id);
      setRunId(detail.latest_analysis_run_id);
    } catch (error) {
      setTurns([{ question: "Open case", error }]);
    }
  }

  async function ask(question: string) {
    if (!caseId || runId === null || question.trim().length < 3) return;
    setBusy(true);
    setTurns((previous) => [...previous, { question }]);
    try {
      const answer = await api.askCase(caseId, runId, question.trim());
      setTurns((previous) => previous.map((t, i) => (i === previous.length - 1 ? { ...t, answer } : t)));
    } catch (error) {
      setTurns((previous) => previous.map((t, i) => (i === previous.length - 1 ? { ...t, error } : t)));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const question = String(new FormData(form).get("question") ?? "");
    void ask(question).then(() => form.reset());
  }

  const cases = casesResult?.data?.items ?? [];
  const ready = canAsk && caseId !== "" && runId !== null;

  return (
    <main className="content">
      <header className="page-header">
        <h1>AstraSync Intelligence</h1>
        <p className="muted">
          Ask about one case. The local model answers only from that case's stored evidence; the
          server checks every citation and number. Answers are screening support for expert review.
        </p>
      </header>
      {!canAsk && <p role="alert">Asking the assistant needs the drafting permission.</p>}
      <div className="agent-layout">
        <section className="panel" aria-labelledby="agent-case">
          <h2 id="agent-case">Case</h2>
          {casesResult === null && <p role="status">Loading cases…</p>}
          {casesResult?.error !== undefined && <p role="alert">{describeError(casesResult.error)}</p>}
          <label className="stacked">
            Case to discuss
            <select value={caseId} onChange={(event) => void selectCase(event.target.value)}>
              <option value="">Choose a case</option>
              {cases.map((item) => (
                <option key={item.case_id} value={item.case_id}>
                  {caseLabel(item)}
                </option>
              ))}
            </select>
          </label>
          {caseId !== "" && runId === null && turns.length === 0 && (
            <p className="muted small">This case has no finished analysis yet; run one from the case page first.</p>
          )}
          <h2>Commands</h2>
          <div className="command-bar" role="group" aria-label="Preset commands">
            {COMMANDS.map((command) => (
              <button
                key={command.label}
                type="button"
                className="command"
                disabled={!ready || busy}
                onClick={() => void ask(command.prompt)}
              >
                {command.label}
              </button>
            ))}
          </div>
        </section>
        <section className="panel chat" aria-labelledby="agent-chat">
          <h2 id="agent-chat">Conversation</h2>
          {turns.length === 0 && <p className="muted">Choose a case, then a command or your own question.</p>}
          <ol className="plain" aria-live="polite">
            {turns.map((turn, index) => (
              <li key={index}>
                <div className="message user">{turn.question}</div>
                {turn.answer && (
                  <div className="message assistant">
                    <p className="pre-wrap">{turn.answer.answer_markdown}</p>
                    <p className="small muted">
                      {turn.answer.cited_evidence_ids.map((id) => (
                        <span key={id} className="citation">evidence {id.slice(-8)}</span>
                      ))}
                      {turn.answer.ai_model_id && <> · {turn.answer.ai_model_id}, local model</>}
                    </p>
                    {turn.answer.uncertainties.length > 0 && (
                      <ul className="small">{turn.answer.uncertainties.map((u) => <li key={u}>{u}</li>)}</ul>
                    )}
                  </div>
                )}
                {turn.error !== undefined && (
                  <div className="message assistant" role="alert">
                    {describeError(turn.error)}
                    {turn.error instanceof ApiError && turn.error.code === "AI_UNAVAILABLE" && (
                      <p className="small muted">The answer was refused by the evidence checks or the local model is unavailable. Try again or rephrase.</p>
                    )}
                  </div>
                )}
                {!turn.answer && turn.error === undefined && (
                  <p role="status" className="muted small">Thinking… local answers can take a few minutes.</p>
                )}
              </li>
            ))}
          </ol>
          <form className="composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="agent-question">Question</label>
            <textarea id="agent-question" name="question" rows={3} maxLength={2000} placeholder="Ask about this case…" disabled={!ready} />
            <button type="submit" className="primary" disabled={!ready || busy}>{busy ? "Asking…" : "Ask"}</button>
          </form>
        </section>
      </div>
    </main>
  );
}
