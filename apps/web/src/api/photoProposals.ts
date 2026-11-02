import { apiFetch, apiUrl } from "./client";
import type { PhotoProposalState } from "./notifications";
import type { Page } from "./reports";

/** A photo a resident offered for a case that has none of its own. */
export type PhotoProposal = {
  id: string;
  master_report_id: string;
  user_id: string;
  storage_key: string;
  state: PhotoProposalState;
  /** when the case's author decided, null while the photo waits */
  decided_at: string | null;
  /** the offered photo, as a path under the api */
  url: string;
  created_at: string;
};

export const photoProposalsApi = {
  /** Offers a photo. The case's author decides whether it stays. */
  offer(masterId: string, photo: File): Promise<PhotoProposal> {
    const form = new FormData();
    form.set("photo", photo, photo.name);
    return apiFetch(
      `/master-reports/${encodeURIComponent(masterId)}/photo-proposals`,
      { method: "POST", body: form },
    );
  },

  /** The case's photos offered by others; only the waiting one by default. */
  list(
    masterId: string,
    params: { state?: PhotoProposalState | null } = {},
    signal?: AbortSignal,
  ): Promise<Page<PhotoProposal>> {
    return apiFetch(
      `/master-reports/${encodeURIComponent(masterId)}/photo-proposals`,
      { query: { state: params.state ?? undefined }, signal },
    );
  },

  approve(id: string): Promise<PhotoProposal> {
    return apiFetch(`/photo-proposals/${encodeURIComponent(id)}/approve`, {
      method: "POST",
    });
  },

  reject(id: string): Promise<PhotoProposal> {
    return apiFetch(`/photo-proposals/${encodeURIComponent(id)}/reject`, {
      method: "POST",
    });
  },

  /** The address an offered photo is served from, given its path under the api. */
  photoUrl(url: string): string {
    return apiUrl(url);
  },
};
