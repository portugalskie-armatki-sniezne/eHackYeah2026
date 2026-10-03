import { apiFetch, apiUrl } from "./client";

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

export type ReportCategory = { id: number; name: string };

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
  edited_at: string;
  created_at: string;
};

/** The detail view adds the photos of every report attached to the master. */
export type MasterReportDetail = MasterReport & { photos: ReportPhoto[] };

export type MasterReportPage = Page<MasterReport>;

export type MasterReportFilters = {
  status_id?: number;
  report_category_id?: number;
  responsible_office_id?: number;
  responsible_service_entity_id?: number;
  limit?: number;
  offset?: number;
};

// the largest page the api serves
const MAX_PAGE_SIZE = 200;

function masterReports(
  params: MasterReportFilters = {},
  signal?: AbortSignal,
): Promise<MasterReportPage> {
  return apiFetch("/master-reports", { query: params, signal });
}

export const reportsApi = {
  categories(signal?: AbortSignal): Promise<ReportCategory[]> {
    return apiFetch("/report-categories", { signal });
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
    params: { user_id?: string; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<ReportPage> {
    return apiFetch("/reports", { query: params, signal });
  },

  masterReports,

  masterReport(id: string, signal?: AbortSignal): Promise<MasterReportDetail> {
    return apiFetch(`/master-reports/${encodeURIComponent(id)}`, { signal });
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

  photoUrl(photo: ReportPhoto): string {
    return apiUrl(photo.url);
  },
};
