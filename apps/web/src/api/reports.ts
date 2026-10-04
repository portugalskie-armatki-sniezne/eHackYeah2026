import { ApiError, apiFetch, apiUrl } from "./client";

export type ReportLocation = {
  longitude: number;
  latitude: number;
};

export type ReportPhoto = {
  id: string;
  report_id: string;
  storage_key: string;
  url: string;
  created_at: string;
};

export type Report = {
  id: string;
  user_id: string;
  master_report_id: string | null;
  report_category_id: number;
  title: string;
  description: string;
  location: ReportLocation;
  municipality_teryt: string | null;
  municipality_name: string | null;
  county_teryt: string | null;
  county_name: string | null;
  photos: ReportPhoto[];
  edited_at: string;
  created_at: string;
};

export type ReportCreate = {
  report_category_id: number;
  title: string;
  description: string;
  location: ReportLocation;
  photos?: File[];
};

/** report_categories.name; picks the pin pictogram */
export type ReportCategoryName = "improvement" | "issue";

export type ReportCategory = { id: number; name: string };

/** master_report_statuses.name, in the order a master moves through them */
export type MasterReportStatusName =
  "created" | "reported" | "inprogress" | "finished";

export type MasterReportStatus = { id: number; name: string };

export type MasterReportComment = {
  id: string;
  master_report_id: string;
  user_id: string;
  author_first_name: string;
  content: string;
  like_count: number;
  /** false without a token */
  liked_by_me: boolean;
  /** an office or admin comment that stands out in the discussion */
  highlighted: boolean;
  created_at: string;
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type ReportPage = Page<Report>;

/** The issue several filings are folded into; what the map draws a pin for. */
export type MasterReport = {
  id: string;
  report_category_id: number;
  status_id: number;
  responsible_office_id: number | null;
  responsible_service_entity_id: number | null;
  title: string;
  description: string;
  location: ReportLocation;
  response: string | null;
  report_count: number;
  /** the earliest photo among the master's reports, as a path under the api, or null */
  photo_url: string | null;
  /** whoever filed the case first, who decides about a photo offered for it */
  author_id: string | null;
  /**
   * A photo a resident offered for a case that has none, which the map and the
   * case's sheet show under a question mark until its author decides about it.
   */
  pending_photo_id: string | null;
  pending_photo_url: string | null;
  edited_at: string;
  created_at: string;
};

/** The detail view adds the photos of every report attached to the master. */
export type MasterReportDetail = MasterReport & { photos: ReportPhoto[] };

export type MasterReportPage = Page<MasterReport>;

/** What office and admin can change on a master; a null clears the response. */
export type MasterReportUpdate = {
  status_id?: number;
  response?: string | null;
};

export type MasterReportFilters = {
  status_id?: number;
  report_category_id?: number;
  responsible_office_id?: number;
  responsible_service_entity_id?: number;
  limit?: number;
  offset?: number;
};

// the largest page the api serves
export const MAX_PAGE_SIZE = 200;

function masterReports(
  params: MasterReportFilters = {},
  signal?: AbortSignal,
): Promise<MasterReportPage> {
  return apiFetch("/master-reports", { query: params, signal });
}

// the reports folded into one master, a page at a time
function masterReportsOf(masterId: string): Promise<ReportPage> {
  return apiFetch("/reports", {
    query: { master_report_id: masterId, limit: MAX_PAGE_SIZE },
  });
}

export const reportsApi = {
  categories(signal?: AbortSignal): Promise<ReportCategory[]> {
    return apiFetch("/report-categories", { signal });
  },

  statuses(signal?: AbortSignal): Promise<MasterReportStatus[]> {
    return apiFetch("/master-report-statuses", { signal });
  },

  create(body: ReportCreate): Promise<Report> {
    const form = new FormData();
    form.set("report_category_id", String(body.report_category_id));
    form.set("title", body.title);
    form.set("description", body.description);
    form.set("longitude", String(body.location.longitude));
    form.set("latitude", String(body.location.latitude));
    for (const photo of body.photos ?? []) {
      form.append("photos", photo, photo.name);
    }
    return apiFetch("/reports", { method: "POST", body: form });
  },

  get(id: string, signal?: AbortSignal): Promise<Report> {
    return apiFetch(`/reports/${encodeURIComponent(id)}`, { signal });
  },

  list(
    params: {
      user_id?: string;
      master_report_id?: string;
      limit?: number;
      offset?: number;
    } = {},
    signal?: AbortSignal,
  ): Promise<ReportPage> {
    return apiFetch("/reports", { query: params, signal });
  },

  deleteReport(id: string): Promise<void> {
    return apiFetch(`/reports/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  masterReports,

  masterReport(id: string, signal?: AbortSignal): Promise<MasterReportDetail> {
    return apiFetch(`/master-reports/${encodeURIComponent(id)}`, { signal });
  },

  updateMasterReport(
    id: string,
    body: MasterReportUpdate,
  ): Promise<MasterReportDetail> {
    return apiFetch(`/master-reports/${encodeURIComponent(id)}`, {
      method: "PATCH",
      json: body,
    });
  },

  deleteMasterReport(id: string): Promise<void> {
    return apiFetch(`/master-reports/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  /**
   * Takes a pin off the map for good: the master cannot be deleted while it
   * has reports, so those go first, each with its photos, and the last one
   * takes the master and its discussion with it. Admin only.
   */
  async removeMaster(id: string): Promise<void> {
    for (;;) {
      const page = await masterReportsOf(id);
      if (page.items.length === 0) break;
      for (const report of page.items) {
        await reportsApi.deleteReport(report.id);
      }
    }
    try {
      await reportsApi.deleteMasterReport(id);
    } catch (error) {
      // already gone with its last report
      if (!(error instanceof ApiError && error.status === 404)) throw error;
    }
  },

  /** Every master report, paged through at the largest page the api serves. */
  async allMasterReports(signal?: AbortSignal): Promise<MasterReport[]> {
    const items: MasterReport[] = [];
    let total = Infinity;
    while (items.length < total) {
      const page = await masterReports(
        { limit: MAX_PAGE_SIZE, offset: items.length },
        signal,
      );
      total = page.total;
      if (page.items.length === 0) break;
      items.push(...page.items);
    }
    return items;
  },

  /**
   * The ids of the cases the account has a filing on, which is what the map's
   * and the list's "only mine" filter narrows to. A case the account filed
   * counts whether or not it was the one that opened it, so this goes through
   * the account's reports rather than the masters' authors.
   */
  async myMasterReportIds(
    userId: string,
    signal?: AbortSignal,
  ): Promise<Set<string>> {
    const ids = new Set<string>();
    let seen = 0;
    let total = Infinity;
    while (seen < total) {
      const page = await reportsApi.list(
        { user_id: userId, limit: MAX_PAGE_SIZE, offset: seen },
        signal,
      );
      total = page.total;
      if (page.items.length === 0) break;
      seen += page.items.length;
      for (const report of page.items) {
        if (report.master_report_id) ids.add(report.master_report_id);
      }
    }
    return ids;
  },

  /** The address a photo is served from, given its path under the api. */
  photoUrl(photo: Pick<ReportPhoto, "url">): string {
    return apiUrl(photo.url);
  },

  /** The master's discussion, oldest first. */
  comments(
    masterId: string,
    signal?: AbortSignal,
  ): Promise<Page<MasterReportComment>> {
    return apiFetch(
      `/master-reports/${encodeURIComponent(masterId)}/comments`,
      { signal },
    );
  },

  // only office and admin may highlight; the api answers 403 otherwise
  addComment(
    masterId: string,
    content: string,
    highlighted = false,
  ): Promise<MasterReportComment> {
    return apiFetch(
      `/master-reports/${encodeURIComponent(masterId)}/comments`,
      { method: "POST", json: { content, highlighted } },
    );
  },

  deleteComment(id: string): Promise<void> {
    return apiFetch(`/comments/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  // both are idempotent and answer with the comment and its current count
  likeComment(id: string): Promise<MasterReportComment> {
    return apiFetch(`/comments/${encodeURIComponent(id)}/like`, {
      method: "PUT",
    });
  },

  unlikeComment(id: string): Promise<MasterReportComment> {
    return apiFetch(`/comments/${encodeURIComponent(id)}/like`, {
      method: "DELETE",
    });
  },
};
