import { useSyncExternalStore } from "react";
import { apiFetch, getToken, onTokenChange } from "./client";
import type { Page } from "./reports";

/**
 * What a notification tells its recipient; the page picks its wording and its
 * action buttons by the kind. Mirrors the API's own list.
 */
export type NotificationKind =
  | "status_inprogress"
  | "status_finished"
  | "comment"
  | "update"
  | "photo_proposal"
  | "photo_approved"
  | "photo_rejected";

export type PhotoProposalState = "pending" | "approved" | "rejected";

export type Notification = {
  id: string;
  user_id: string;
  kind: NotificationKind;
  /** the case this is about, null once it has been taken off the map */
  master_report_id: string | null;
  photo_proposal_id: string | null;
  /** the case's title as it read when this happened */
  subject: string;
  /** a comment, an official response, or nothing */
  detail: string | null;
  /** whether an offered photo still waits, so the decide buttons still apply */
  photo_proposal_state: PhotoProposalState | null;
  /** the offered photo, as a path under the api */
  photo_proposal_url: string | null;
  read_at: string | null;
  created_at: string;
};

export type UnreadCount = { count: number };

export const notificationsApi = {
  list(
    params: { unread?: boolean; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<Page<Notification>> {
    return apiFetch("/notifications", {
      query: { ...params, unread: params.unread ? "true" : undefined },
      signal,
    });
  },

  unreadCount(signal?: AbortSignal): Promise<UnreadCount> {
    return apiFetch("/notifications/unread-count", { signal });
  },

  // idempotent, a second call keeps the first timestamp
  markRead(id: string): Promise<Notification> {
    return apiFetch(`/notifications/${encodeURIComponent(id)}/read`, {
      method: "PUT",
    });
  },

  markAllRead(): Promise<UnreadCount> {
    return apiFetch("/notifications/read-all", { method: "POST" });
  },

  dismiss(id: string): Promise<void> {
    return apiFetch(`/notifications/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },
};

let unread = 0;
const listeners = new Set<() => void>();

function setUnread(next: number) {
  if (next === unread) {
    return;
  }
  unread = next;
  for (const listener of listeners) listener();
}

/**
 * Reads the navbar badge's figure again; signed out it is zero. Called after
 * anything that opens or clears a notification, so the badge keeps up.
 */
export async function refreshUnreadCount(): Promise<void> {
  if (!getToken()) {
    setUnread(0);
    return;
  }
  try {
    setUnread((await notificationsApi.unreadCount()).count);
  } catch {
    // a failed read leaves the badge showing what it showed before
  }
}

// a sign-in brings its own notifications along, and a sign-out leaves none
onTokenChange(() => void refreshUnreadCount());
if (getToken()) void refreshUnreadCount();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** How many notifications the signed-in account has not opened yet. */
export function useUnreadCount(): number {
  return useSyncExternalStore(subscribe, () => unread);
}
