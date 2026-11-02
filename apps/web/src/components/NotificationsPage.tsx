import { useEffect, useMemo, useState } from "react";
import {
  notificationsApi,
  refreshUnreadCount,
  type Notification,
  type NotificationKind,
} from "../api/notifications";
import { photoProposalsApi } from "../api/photoProposals";
import type { SessionState } from "../api/session";
import { useLocale, useMessages } from "../i18n/locale";
import type { Messages } from "../i18n/messages";
import { useTourActive } from "./onboardingState";
import { formatDate, timeAgo } from "./relativeTime";
import { caseHash } from "./useHashRoute";
import "./NotificationsPage.css";

type NotificationsPageProps = {
  session: SessionState;
  /** Called when a signed-out visitor opens the page. */
  onSignIn: () => void;
};

type NotificationsMessages = Messages["notifications"];

// the mark on the card's corner, picked the way the pins pick theirs
const KIND_GLYPHS: Record<NotificationKind, string> = {
  status_inprogress: "~",
  status_finished: "✓",
  comment: "”",
  update: "≡",
  photo_proposal: "?",
  photo_approved: "✓",
  photo_rejected: "×",
};

function errorText(error: unknown, t: NotificationsMessages) {
  return error instanceof Error ? error.message : t.somethingWrong;
}

/**
 * Everything that happened to the cases the account filed, newest first: a
 * case taken up or finished, a comment under it, an office's update, and a
 * photo a neighbour offered for it, which this page is where you take or turn
 * down. It takes the map's place on the sheet, like the reports page.
 */
export default function NotificationsPage({
  session,
  onSignIn,
}: NotificationsPageProps) {
  const allMessages = useMessages();
  const t = allMessages.notifications;
  const tourActive = useTourActive();
  const [items, setItems] = useState<Notification[] | null>(null);
  const [demoItems, setDemoItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const signedIn = session.status === "signed-in";

  const sampleItems: Notification[] = useMemo(() => {
    const now = new Date();
    return allMessages.onboarding.sampleNotifications.map((sample, idx) => ({
      id: `demo-${idx}`,
      user_id: "demo-user",
      kind: sample.kind,
      master_report_id: "demo",
      photo_proposal_id: null,
      subject: sample.subject,
      detail: sample.detail,
      photo_proposal_state: null,
      photo_proposal_url: null,
      read_at:
        idx === 0 ? null : new Date(now.getTime() - 3600000).toISOString(),
      created_at: new Date(now.getTime() - (idx + 1) * 1800000).toISOString(),
    }));
  }, [allMessages]);

  const activeItems = signedIn
    ? items
    : tourActive
      ? (demoItems ?? sampleItems)
      : null;
  const showList = signedIn || tourActive;

  // A session that ended takes its notifications with it, so the next sign-in
  // does not open on the previous account's list.
  if (items !== null && !signedIn) {
    setItems(null);
  }

  useEffect(() => {
    if (!signedIn) {
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    notificationsApi.list({}, signal).then(
      (page) => {
        if (!signal.aborted) setItems(page.items);
      },
      (error) => {
        if (!signal.aborted) setError(errorText(error, t));
      },
    );
    return () => controller.abort();
    // the strings only matter for the fallback message
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn]);

  const replace = (next: Notification) => {
    if (!signedIn && tourActive) {
      setDemoItems((current) =>
        (current ?? sampleItems).map((item) =>
          item.id === next.id ? next : item,
        ),
      );
      return;
    }
    setItems(
      (current) =>
        current?.map((item) => (item.id === next.id ? next : item)) ?? null,
    );
  };

  // a decision on an offered photo settles every notification about it
  const settleProposal = (proposalId: string, state: "approved" | "rejected") =>
    setItems(
      (current) =>
        current?.map((item) =>
          item.photo_proposal_id === proposalId
            ? { ...item, photo_proposal_state: state }
            : item,
        ) ?? null,
    );

  const drop = (id: string) => {
    if (!signedIn && tourActive) {
      setDemoItems((current) =>
        (current ?? sampleItems).filter((item) => item.id !== id),
      );
      return;
    }
    setItems((current) => current?.filter((item) => item.id !== id) ?? null);
  };

  const markAllRead = async () => {
    if (!signedIn && tourActive) {
      const now = new Date().toISOString();
      setDemoItems((current) =>
        (current ?? sampleItems).map((item) =>
          item.read_at ? item : { ...item, read_at: now },
        ),
      );
      return;
    }
    setError(null);
    try {
      await notificationsApi.markAllRead();
      const now = new Date().toISOString();
      setItems(
        (current) =>
          current?.map((item) =>
            item.read_at ? item : { ...item, read_at: now },
          ) ?? null,
      );
      void refreshUnreadCount();
    } catch (error) {
      setError(errorText(error, t));
    }
  };

  const shown = (activeItems ?? []).filter(
    (item) => !unreadOnly || !item.read_at,
  );
  const unreadCount = (activeItems ?? []).filter(
    (item) => !item.read_at,
  ).length;

  return (
    <section
      className="notifications-page"
      aria-labelledby="notifications-title"
    >
      <div className="notifications-page__frame">
        <div className="notifications-page__sheet">
          <header className="notifications-page__header">
            <h1 id="notifications-title" className="notifications-page__title">
              {t.title}
            </h1>
            <p className="notifications-page__lede">{t.lede}</p>
            <a className="notifications-page__button" href="#map">
              {t.backToMap}
            </a>
          </header>

          {!showList ? (
            <div className="notifications-page__notice">
              <div>
                <p className="notifications-page__notice-title">
                  {t.signedOutTitle}
                </p>
                <p className="notifications-page__hint">{t.signedOutText}</p>
              </div>
              {session.status === "signed-out" && (
                <button
                  type="button"
                  className="notifications-page__button notifications-page__button--primary"
                  onClick={onSignIn}
                >
                  {t.signIn}
                </button>
              )}
            </div>
          ) : (
            <>
              {!signedIn && tourActive && (
                <p className="notifications-page__demo-banner" role="note">
                  {allMessages.onboarding.sampleBanner}
                </p>
              )}
              <div className="notifications-page__controls">
                <div
                  className="notifications-page__pills"
                  role="group"
                  aria-label={t.filter}
                >
                  <button
                    type="button"
                    className="notifications-page__pill"
                    aria-pressed={!unreadOnly}
                    onClick={() => setUnreadOnly(false)}
                  >
                    {t.all}
                  </button>
                  <button
                    type="button"
                    className="notifications-page__pill"
                    aria-pressed={unreadOnly}
                    onClick={() => setUnreadOnly(true)}
                  >
                    {t.unreadOnly}
                    {unreadCount > 0 && (
                      <span className="notifications-page__tally">
                        {unreadCount}
                      </span>
                    )}
                  </button>
                </div>
                {activeItems && (
                  <p className="notifications-page__count">
                    {t.shown(shown.length, activeItems.length)}
                  </p>
                )}
                <button
                  type="button"
                  className="notifications-page__button"
                  disabled={unreadCount === 0}
                  onClick={() => void markAllRead()}
                >
                  {t.markAllRead}
                </button>
              </div>

              {error && (
                <p className="notifications-page__error" role="alert">
                  {error}
                </p>
              )}

              {activeItems === null && !error ? (
                <p className="notifications-page__state">{t.loading}</p>
              ) : shown.length === 0 ? (
                <p className="notifications-page__state">
                  {unreadOnly ? t.emptyUnread : t.empty}
                </p>
              ) : (
                <ul className="notifications-page__list">
                  {shown.map((item) => (
                    <li key={item.id}>
                      <NotificationCard
                        notification={item}
                        onChange={replace}
                        onSettled={settleProposal}
                        onDismissed={() => drop(item.id)}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}

type NotificationCardProps = {
  notification: Notification;
  onChange: (notification: Notification) => void;
  onSettled: (proposalId: string, state: "approved" | "rejected") => void;
  onDismissed: () => void;
};

/**
 * One thing that happened, as a paper slip: what it was, which case it was
 * about, and the buttons that act on it. An offered photo is decided here.
 */
function NotificationCard({
  notification,
  onChange,
  onSettled,
  onDismissed,
}: NotificationCardProps) {
  const t = useMessages().notifications;
  const locale = useLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unread = notification.read_at === null;
  const proposalId = notification.photo_proposal_id;
  const waiting =
    notification.kind === "photo_proposal" &&
    notification.photo_proposal_state === "pending";
  const photoUrl = notification.photo_proposal_url;

  const run = async (task: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (error) {
      setError(errorText(error, t));
    } finally {
      setBusy(false);
    }
  };

  // every button here has been acted on, so the notification counts as read
  const read = async () => {
    if (!unread) return;
    if (notification.id.startsWith("demo-")) {
      onChange({ ...notification, read_at: new Date().toISOString() });
      return;
    }
    onChange(await notificationsApi.markRead(notification.id));
    void refreshUnreadCount();
  };

  const decide = (approve: boolean) =>
    run(async () => {
      if (!proposalId) return;
      const decided = approve
        ? await photoProposalsApi.approve(proposalId)
        : await photoProposalsApi.reject(proposalId);
      onSettled(
        proposalId,
        decided.state === "approved" ? "approved" : "rejected",
      );
      await read();
    });

  return (
    <article
      className={
        unread
          ? "notifications-page__card notifications-page__card--unread"
          : "notifications-page__card"
      }
    >
      <span className="notifications-page__glyph" aria-hidden="true">
        {KIND_GLYPHS[notification.kind]}
      </span>

      <div className="notifications-page__body">
        <div className="notifications-page__meta">
          <span className="notifications-page__kind">
            {t.kinds[notification.kind]}
          </span>
          {unread && (
            <span className="notifications-page__new">{t.unread}</span>
          )}
          <time
            className="notifications-page__when"
            dateTime={notification.created_at}
            title={formatDate(notification.created_at, locale)}
          >
            {timeAgo(notification.created_at, locale, t.justNow)}
          </time>
        </div>

        <p className="notifications-page__subject">{notification.subject}</p>

        {notification.detail && (
          <p className="notifications-page__detail">{notification.detail}</p>
        )}

        {photoUrl && (
          <img
            className="notifications-page__photo"
            src={photoProposalsApi.photoUrl(photoUrl)}
            alt={t.offeredPhotoAlt(notification.subject)}
          />
        )}

        {notification.kind === "photo_proposal" && !waiting && (
          <p className="notifications-page__hint">{t.alreadyDecided}</p>
        )}

        {!notification.master_report_id && (
          <p className="notifications-page__hint">{t.caseGone}</p>
        )}

        {error && (
          <p className="notifications-page__error" role="alert">
            {error}
          </p>
        )}

        <div className="notifications-page__actions">
          {waiting && (
            <>
              <button
                type="button"
                className="notifications-page__button notifications-page__button--primary"
                disabled={busy}
                onClick={() => void decide(true)}
              >
                {busy ? t.deciding : t.usePhoto}
              </button>
              <button
                type="button"
                className="notifications-page__button"
                disabled={busy}
                onClick={() => void decide(false)}
              >
                {t.turnDownPhoto}
              </button>
            </>
          )}
          {notification.master_report_id && (
            <a
              className="notifications-page__button"
              href={
                notification.id.startsWith("demo-")
                  ? "#map"
                  : caseHash(notification.master_report_id)
              }
              onClick={() => void run(read)}
            >
              {t.openCase}
            </a>
          )}
          {unread && (
            <button
              type="button"
              className="notifications-page__button"
              disabled={busy}
              onClick={() => void run(read)}
            >
              {t.markRead}
            </button>
          )}
          <button
            type="button"
            className="notifications-page__button notifications-page__button--quiet"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                if (!notification.id.startsWith("demo-")) {
                  await notificationsApi.dismiss(notification.id);
                  void refreshUnreadCount();
                }
                onDismissed();
              })
            }
          >
            {t.dismiss}
          </button>
        </div>
      </div>
    </article>
  );
}
