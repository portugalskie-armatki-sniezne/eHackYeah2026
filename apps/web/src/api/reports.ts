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

  return {
    categories(signal?: AbortSignal): Promise<ReportCategory[]> {
      return request("/report-categories", { signal });
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
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined) query.set(key, String(value));
      }
      return request(`/reports?${query}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
    },

    photoUrl(photo: ReportPhoto): string {
      return `${base}${photo.url}`;
    },
  };
}
