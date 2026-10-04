import { apiFetch } from "./client";

export type ProjectSummary = {
  id: number;
  slug: string;
  title: string;
  category: string;
  category_slug: string | null;
  url: string;
  description: string | null;
  problem: string | null;
  target_group: string | null;
  beneficiaries: string | null;
  effectiveness: string | null;
  authors: string | null;
  summary: string;
  created_at: string;
};

export type ProjectCategory = {
  category: string;
  category_slug: string | null;
  count: number;
};

export type ProjectSearchResult = {
  id: number;
  slug: string;
  title: string;
  category: string;
  category_slug: string | null;
  url: string;
  description: string | null;
  summary: string;
  matched_snippet: string | null;
  score: number;
};

export type ProjectPage = {
  items: ProjectSummary[];
  total: number;
  limit: number;
  offset: number;
};

export const projectsApi = {
  list(
    params: {
      category?: string;
      q?: string;
      limit?: number;
      offset?: number;
    } = {},
    signal?: AbortSignal,
  ): Promise<ProjectPage> {
    return apiFetch("/projects", { query: params, signal });
  },

  categories(signal?: AbortSignal): Promise<ProjectCategory[]> {
    return apiFetch("/projects/categories", { signal });
  },

  get(slug: string, signal?: AbortSignal): Promise<ProjectSummary> {
    return apiFetch(`/projects/${encodeURIComponent(slug)}`, { signal });
  },

  search(
    query: string,
    options: {
      category?: string;
      limit?: number;
    } = {},
    signal?: AbortSignal,
  ): Promise<ProjectSearchResult[]> {
    return apiFetch("/projects/search", {
      method: "POST",
      json: {
        query,
        category: options.category,
        limit: options.limit ?? 5,
      },
      signal,
    });
  },
};
