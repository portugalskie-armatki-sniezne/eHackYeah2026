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

export type ReportPage = {
  items: Report[];
  total: number;
  limit: number;
  offset: number;
};

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

  photoUrl(photo: ReportPhoto): string {
    return apiUrl(photo.url);
  },
};
