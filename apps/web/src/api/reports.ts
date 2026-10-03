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

export class ReportApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ReportApiError";
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item: unknown) => {
        if (!item || typeof item !== "object" || !("msg" in item)) return [];
        if (typeof item.msg !== "string") return [];
        const field =
          "loc" in item && Array.isArray(item.loc)
            ? item.loc.slice(1).join(".")
            : "";
        return [field ? `${field}: ${item.msg}` : item.msg];
      });
      if (messages.length) return messages.join("; ");
    }
  }
  return `Report request failed (${status}).`;
}

function queryString(params: Record<string, number | string | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value));
  }
  return query.toString();
}

export function createReportsApi(baseUrl: string) {
  const base = baseUrl.replace(/\/+$/, "");

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${base}${path}`, options);
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new ReportApiError(
        response.status,
        errorMessage(body, response.status),
      );
    }
    return response.json() as Promise<T>;
  }

  // the public endpoints take no token, but one is sent when given so a backend
  // that guards them answers the same way
  function authorization(token?: string): HeadersInit {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function masterReports(
    params: MasterReportFilters = {},
    signal?: AbortSignal,
    token?: string,
  ): Promise<MasterReportPage> {
    return request(`/master-reports?${queryString(params)}`, {
      headers: authorization(token),
      signal,
    });
  }

  return {
    categories(
      signal?: AbortSignal,
      token?: string,
    ): Promise<ReportCategory[]> {
      return request("/report-categories", {
        headers: authorization(token),
        signal,
      });
    },

    create(body: ReportCreate, token: string): Promise<Report> {
      const form = new FormData();
      form.set("report_category_id", String(body.report_category_id));
      form.set("title", body.title);
      form.set("description", body.description);
      form.set("longitude", String(body.location.longitude));
      form.set("latitude", String(body.location.latitude));
      for (const photo of body.photos ?? []) {
        form.append("photos", photo, photo.name);
      }
      return request("/reports", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
    },

    get(id: string, token: string, signal?: AbortSignal): Promise<Report> {
      return request(`/reports/${encodeURIComponent(id)}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
    },

    list(
      token: string,
      params: { user_id?: string; limit?: number; offset?: number } = {},
      signal?: AbortSignal,
    ): Promise<ReportPage> {
      return request(`/reports?${queryString(params)}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
    },

    masterReports,

    masterReport(
      id: string,
      signal?: AbortSignal,
      token?: string,
    ): Promise<MasterReportDetail> {
      return request(`/master-reports/${encodeURIComponent(id)}`, {
        headers: authorization(token),
        signal,
      });
    },

    /** Every master report, paged through at the largest page the api serves. */
    async allMasterReports(
      signal?: AbortSignal,
      token?: string,
    ): Promise<MasterReport[]> {
      const items: MasterReport[] = [];
      let total = Infinity;
      while (items.length < total) {
        const page = await masterReports(
          { limit: MAX_PAGE_SIZE, offset: items.length },
          signal,
          token,
        );
        total = page.total;
        if (page.items.length === 0) break;
        items.push(...page.items);
      }
      return items;
    },

    photoUrl(photo: ReportPhoto): string {
      return `${base}${photo.url}`;
    },
  };
}

// the Vite dev server proxies /api to the local backend; deployed builds get the
// api origin at build time from VITE_API_URL
export const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? "/api";

export const reportsApi = createReportsApi(API_BASE_URL);
