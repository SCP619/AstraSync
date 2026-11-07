/**
 * Source upload and processing status (workflow A, TR-SRC-006/007, TR-UX-007). Every step is a real
 * API call: upload session → parts → complete with the SHA-256 → job polling. The server verifies
 * size and hash and decides the outcome; this page only reports what it says.
 *
 * Browsers cannot hash a file incrementally, so the page refuses files above BROWSER_LIMIT_BYTES
 * and says to use the resumable command-line upload instead (benchmarks/stage6.py shows the flow).
 */
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { Schemas } from "../api/client";
import { describeError, RequestId, useLoad, useSession } from "../shared";

export const BROWSER_LIMIT_BYTES = 256 * 1024 * 1024;
const TERMINAL = new Set<Schemas["PipelineStatus"]>(["READY", "PARTIAL", "FAILED", "CANCELLED", "QUARANTINED"]);
const POLL_MS = 2000;

const STATUS_TEXT: Partial<Record<Schemas["PipelineStatus"], string>> = {
  READY: "Ready: verified, archived and indexed.",
  PARTIAL: "Partial: bytes verified and archived, but not indexed (for example, no parser for this source type).",
  FAILED: "Failed. The original is not changed; see the error code.",
  CANCELLED: "Cancelled.",
  QUARANTINED: "Quarantined: the file failed verification or was refused by its parser. It is not used.",
};

type Step = { kind: "idle" } | { kind: "hashing" } | { kind: "sending"; sent: number; total: number }
  | { kind: "completing" } | { kind: "processing"; upload: Schemas["UploadSession"]; job: Schemas["JobRun"] | null }
  | { kind: "failed"; error: unknown };

async function sha256Hex(file: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} bytes`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 / 1024).toFixed(1)} MiB`;
}

export function UploadPage() {
  const { api } = useSession();
  const loadSources = useCallback((signal: AbortSignal) => api.listSources(signal), [api]);
  const { result: sources } = useLoad(loadSources);
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [invalid, setInvalid] = useState<string | null>(null);
  const active = useRef(true);
  useEffect(() => {
    // Set on every mount: React's development mode mounts, cleans up and mounts again.
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);

  async function poll(upload: Schemas["UploadSession"]) {
    let current = upload;
    while (active.current) {
      const job = current.job_id ? await api.getJob(current.job_id) : null;
      if (!active.current) return;
      setStep({ kind: "processing", upload: current, job });
      if (job !== null && TERMINAL.has(job.status)) return;
      if (job === null && TERMINAL.has(current.status)) return;
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      current = await api.getUpload(current.upload_id);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement | null;
    const file = input?.files?.[0] ?? null;
    const source = sources?.data?.items.find((item) => item.source_id === data.get("source"));
    if (file === null || file.size === 0 || source === undefined) {
      setInvalid("Choose a source and a non-empty file.");
      return;
    }
    if (file.size > BROWSER_LIMIT_BYTES) {
      setInvalid(
        `This file is ${formatBytes(file.size)}. Files above ${formatBytes(BROWSER_LIMIT_BYTES)} must use the resumable command-line upload.`,
      );
      return;
    }
    setInvalid(null);
    try {
      setStep({ kind: "hashing" });
      const contentSha256 = await sha256Hex(file);
      const session = await api.createUpload({
        source_id: source.source_id,
        source_type: source.source_type,
        usage_classification: source.usage_classification,
        filename_original: file.name,
        expected_size_bytes: file.size,
        content_sha256: contentSha256,
      });
      const total = Math.max(1, Math.ceil(file.size / session.part_size_bytes));
      for (let number = 1; number <= total; number += 1) {
        setStep({ kind: "sending", sent: number - 1, total });
        const start = (number - 1) * session.part_size_bytes;
        await api.putUploadPart(session.upload_id, number, file.slice(start, start + session.part_size_bytes));
      }
      setStep({ kind: "completing" });
      const state = await api.getUpload(session.upload_id);
      const parts = state.parts
        .filter((part) => part.received && part.etag !== null)
        .map((part) => ({ part_number: part.part_number, etag: part.etag as string }))
        .sort((a, b) => a.part_number - b.part_number);
      const completed = await api.completeUpload(session.upload_id, { parts, content_sha256: contentSha256 });
      await poll(completed);
    } catch (error) {
      if (active.current) setStep({ kind: "failed", error });
    }
  }

  const busy = step.kind === "hashing" || step.kind === "sending" || step.kind === "completing";
  const items = sources?.data?.items ?? [];

  return (
    <main className="content">
      <h1>Upload a source file</h1>
      <p className="muted">
        The server checks the size and SHA-256, archives the original unchanged and then parses it.
        Nothing here edits source content.
      </p>
      {sources === null && <p role="status">Loading sources…</p>}
      {sources?.error !== undefined && (
        <div role="alert">
          <p>{describeError(sources.error)}</p>
          <RequestId error={sources.error} />
        </div>
      )}
      {sources?.data !== undefined && items.length === 0 && (
        <p>No sources are registered for your organisation. An administrator registers sources first.</p>
      )}
      {items.length > 0 && (
        <form className="panel filters" onSubmit={(event) => void submit(event)} aria-label="Upload">
          <label>
            Source
            <select name="source" required defaultValue="">
              <option value="" disabled>Choose a source</option>
              {items.map((item) => (
                <option key={item.source_id} value={item.source_id}>
                  {item.source_id} ({item.source_type}, {item.usage_classification}
                  {item.is_synthetic ? ", synthetic" : ""})
                </option>
              ))}
            </select>
          </label>
          <label>
            File
            <input name="file" type="file" required />
          </label>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>
      )}
      {invalid !== null && <p role="alert">{invalid}</p>}
      <section className="panel" aria-live="polite" aria-labelledby="upload-status">
        <h2 id="upload-status">Status</h2>
        {step.kind === "idle" && <p className="muted">No upload in progress.</p>}
        {step.kind === "hashing" && <p>Computing the SHA-256 on this device…</p>}
        {step.kind === "sending" && (
          <p>
            Sending part {step.sent + 1} of {step.total}…{" "}
            <progress max={step.total} value={step.sent} aria-label="Parts sent" />
          </p>
        )}
        {step.kind === "completing" && <p>Asking the server to verify the file…</p>}
        {step.kind === "processing" && (
          <dl>
            <dt>Upload</dt>
            <dd><code>{step.upload.upload_id}</code> ({formatBytes(step.upload.received_size_bytes)} received)</dd>
            <dt>Server SHA-256</dt>
            <dd><code>{step.upload.content_sha256 ?? "not yet verified"}</code></dd>
            <dt>Job</dt>
            <dd>
              {step.job === null ? (
                <code>{step.upload.status}</code>
              ) : (
                <>
                  <code>{step.job.status}</code>
                  {step.job.progress_stage && <span className="muted"> · {step.job.progress_stage}</span>}
                  {step.job.processed_records !== null && (
                    <span className="muted"> · {step.job.processed_records} records</span>
                  )}
                  {step.job.attempt > 1 && <span className="muted"> · attempt {step.job.attempt}</span>}
                  {step.job.error_code && <span> · error <code>{step.job.error_code}</code></span>}
                </>
              )}
            </dd>
            {(() => {
              const status = step.job?.status ?? step.upload.status;
              const text = STATUS_TEXT[status];
              return text ? (
                <>
                  <dt>Result</dt>
                  <dd>
                    {text} {status === "READY" && <Link to="/sources">Open the source library</Link>}
                  </dd>
                </>
              ) : null;
            })()}
          </dl>
        )}
        {step.kind === "failed" && (
          <div role="alert">
            <p>{describeError(step.error)}</p>
            <RequestId error={step.error} />
            <p className="muted small">Uploaded parts are kept by the server until the session expires.</p>
          </div>
        )}
      </section>
    </main>
  );
}
