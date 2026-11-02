import { ApiError, apiFetch, apiUrl } from "./client";
import type { Page } from "./reports";

/**
 * One generation job of the api's visualization queue: Gemini's picture drawn
 * over the report's photos, a fault repaired or an idea carried out. The file
 * is public once the report is published; the job itself is the author's and
 * an admin's.
 */
export type Visualization = {
  id: string;
  draft_id: string | null;
  report_id: string | null;
  /** what the picture shows; mirrors ReportCategoryName of the API */
  report_type: "improvement" | "issue";
  status: "queued" | "running" | "succeeded" | "failed";
  prompt: string | null;
  media_type: string | null;
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
  generated: true;
  /** the drawn picture as a path under the api, once saved and still available */
  url: string | null;
};

// how often a queued or running job is asked again
const POLL_MS = 3000;

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

/** The job the api says is already running for this account, if the error names one. */
export function activeJobId(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body;
  if (!body || typeof body !== "object" || !("detail" in body)) return null;
  const detail = body.detail;
  if (!detail || typeof detail !== "object" || !("job_id" in detail)) {
    return null;
  }
  return typeof detail.job_id === "string" ? detail.job_id : null;
}

export const visualizationsApi = {
  /** The case's successful pictures, newest first; public. */
  history(
    masterId: string,
    signal?: AbortSignal,
  ): Promise<Page<Visualization>> {
    return apiFetch(
      `/master-reports/${encodeURIComponent(masterId)}/visualizations`,
      { signal },
    );
  },

  /**
   * Queues a picture for a published report, from its saved description and
   * photos. Author or admin only; the key makes a retried request return the
   * same job instead of a second one.
   */
  generate(
    reportId: string,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<Visualization> {
    return apiFetch(`/reports/${encodeURIComponent(reportId)}/visualizations`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      signal,
    });
  },

  /** The job's current state; author or admin only. */
  status(jobId: string, signal?: AbortSignal): Promise<Visualization> {
    return apiFetch(`/visualizations/${encodeURIComponent(jobId)}`, {
      signal,
    });
  },

  /** Asks after the job until it has succeeded or failed. */
  async follow(
    job: Visualization,
    signal?: AbortSignal,
  ): Promise<Visualization> {
    let current = job;
    while (current.status === "queued" || current.status === "running") {
      await wait(POLL_MS, signal);
      current = await visualizationsApi.status(current.id, signal);
    }
    return current;
  },

  /** The address the picture is served from, given its path under the api. */
  fileUrl(visualization: { url: string }): string {
    return apiUrl(visualization.url);
  },
};
