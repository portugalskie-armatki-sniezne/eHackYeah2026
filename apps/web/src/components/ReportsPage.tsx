import { useEffect, useId, useState, type FormEvent } from "react";
import {
  reportsApi,
  type MasterReport,
  type MasterReportComment,
  type MasterReportStatus,
  type MasterReportStatusName,
  type ReportCategoryName,
} from "../api/reports";
import { photoProposalsApi } from "../api/photoProposals";
import { isStaff, type SessionState } from "../api/session";
import { useLocale, useMessages } from "../i18n/locale";
import type { Messages } from "../i18n/messages";
import PhotoProposalDialog from "./PhotoProposalDialog";
import StatusBadge from "./StatusBadge";
import useMyCases from "./useMyCases";
import "./ReportsPage.css";

type ReportsPageProps = {
  session: SessionState;
  /** Called when a signed-out visitor tries to comment. */
  onSignIn: () => void;
};

type ReportsMessages = Messages["reports"];

/** What the signed-in account may do on the page. */
type Powers = {
  /** the viewer's id, null when signed out */
  me: string | null;
  /** office and admin: set the status and post highlighted comments */
  staff: boolean;
  /** admin: take a case off the map */
  admin: boolean;
};

// what an empty photo frame is stamped with, as on the map's sheet
const KIND_GLYPHS: Record<ReportCategoryName, string> = {
  issue: "!",
  improvement: "+",
};

// the four statuses the badge knows, in the order a case moves through them
const STATUS_ORDER: MasterReportStatusName[] = [
  "created",
  "reported",
  "inprogress",
  "finished",
];

function isStatusName(name: string): name is MasterReportStatusName {
  return (STATUS_ORDER as string[]).includes(name);
}

function isCategoryName(name: string): name is ReportCategoryName {
  return name === "issue" || name === "improvement";
}

/** One of the row's toggles: what it reads, whether it is on, and its switch. */
type Pill = {
  key: string;
  label: string;
  /** spelled out on hover where the word alone does not say enough */
  hint?: string;
  pressed: boolean;
  press: () => void;
};

function errorText(error: unknown, t: ReportsMessages) {
  return error instanceof Error ? error.message : t.somethingWrong;
}

function statusLabel(name: string, t: ReportsMessages): string {
  return isStatusName(name) ? t.statuses[name] : name;
}

/**
 * Every case on the map as a list anyone can read: its status, its text, and
 * the discussion folded under it. Signed-in residents comment; office and
 * admin accounts also move the case along and answer it with an official
 * comment, and admins can take it off the map. It takes the map's place on
 * the sheet, like the about page.
 */
export default function ReportsPage({ session, onSignIn }: ReportsPageProps) {
  const t = useMessages().reports;
  const [masters, setMasters] = useState<MasterReport[] | null>(null);
  const [statuses, setStatuses] = useState<MasterReportStatus[]>([]);
  const [categories, setCategories] = useState<Map<number, string>>(
    () => new Map(),
  );
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<number | null>(null);
  const [mineOnly, setMineOnly] = useState(false);
  const [query, setQuery] = useState("");
  // the viewer's own cases, which the author pill narrows the list to; null
  // while signed out or still being read, and then the pill is not offered
  const { cases: myCases } = useMyCases();
  const powers: Powers = {
    me: session.status === "signed-in" ? session.user.id : null,
    staff: isStaff(session),
    admin: session.status === "signed-in" && session.user.role === "admin",
  };

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const [all, statusList, categoryList] = await Promise.all([
          reportsApi.allMasterReports(signal),
          reportsApi.statuses(signal),
          reportsApi.categories(signal),
        ]);
        if (signal.aborted) return;
        setMasters(all);
        setStatuses(statusList);
        setCategories(
          new Map(categoryList.map((item) => [item.id, item.name])),
        );
      } catch (error) {
        if (signal.aborted) return;
        setError(errorText(error, t));
      }
    }
    void load();
    return () => controller.abort();
    // the strings only matter for the fallback message
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const replaceMaster = (next: MasterReport) =>
    setMasters(
      (current) =>
        current?.map((master) => (master.id === next.id ? next : master)) ??
        null,
    );

  const dropMaster = (id: string) =>
    setMasters(
      (current) => current?.filter((master) => master.id !== id) ?? null,
    );

  // the known statuses in their order, then any the database adds
  const orderedStatuses = [...statuses].sort(
    (a, b) =>
      (isStatusName(a.name)
        ? STATUS_ORDER.indexOf(a.name)
        : STATUS_ORDER.length) -
      (isStatusName(b.name)
        ? STATUS_ORDER.indexOf(b.name)
        : STATUS_ORDER.length),
  );

  // Signing out takes the author pill away with the list behind it, so the
  // narrowing lifts with it rather than leaving an empty list with nothing to
  // undo; signing back in restores it.
  const mine = mineOnly && myCases !== null;

  // The row the controls carry: every status to narrow to, and, for an account
  // whose own cases are known, the one that keeps just those. "All" is the
  // cleared state of the statuses, so a case list narrowed to the viewer's own
  // stays narrowed when it is pressed.
  const pills: Pill[] = [
    {
      key: "all",
      label: t.allStatuses,
      pressed: statusFilter === null,
      press: () => setStatusFilter(null),
    },
    ...orderedStatuses.map((status) => ({
      key: `status-${status.id}`,
      label: statusLabel(status.name, t),
      pressed: statusFilter === status.id,
      press: () =>
        setStatusFilter(statusFilter === status.id ? null : status.id),
    })),
  ];
  if (myCases !== null) {
    pills.push({
      key: "mine",
      label: t.onlyMine,
      hint: t.onlyMineHint,
      pressed: mine,
      press: () => setMineOnly((current) => !current),
    });
  }

  const needle = query.trim().toLocaleLowerCase();
  const shown = (masters ?? []).filter(
    (master) =>
      (statusFilter === null || master.status_id === statusFilter) &&
      (!mine || myCases.has(master.id)) &&
      (needle === "" ||
        master.title.toLocaleLowerCase().includes(needle) ||
        master.description.toLocaleLowerCase().includes(needle)),
  );

  return (
    <section className="reports-page" aria-labelledby="reports-title">
      <div className="reports-page__frame">
        <div className="reports-page__sheet">
          <header className="reports-page__header">
            <h1 id="reports-title" className="reports-page__title">
              {t.title}
            </h1>
            <p className="reports-page__lede">{t.lede}</p>
            <a className="reports-page__button" href="#map">
              {t.backToMap}
            </a>
          </header>

          <div className="reports-page__controls">
            <label className="reports-page__search">
              <span className="visually-hidden">{t.search}</span>
              <input
                type="search"
                className="reports-page__input"
                placeholder={t.searchPlaceholder}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div
              className="reports-page__pills"
              role="group"
              aria-label={t.filter}
            >
              {pills.map((pill) => (
                <button
                  key={pill.key}
                  type="button"
                  className="reports-page__pill"
                  aria-pressed={pill.pressed}
                  title={pill.hint}
                  onClick={pill.press}
                >
                  {pill.label}
                </button>
              ))}
            </div>
            {masters && (
              <p className="reports-page__count">
                {t.shown(shown.length, masters.length)}
              </p>
            )}
          </div>

          {error && (
            <p className="reports-page__error" role="alert">
              {error}
            </p>
          )}

          {masters === null && !error ? (
            <p className="reports-page__state">{t.loading}</p>
          ) : shown.length === 0 ? (
            <p className="reports-page__state">{t.empty}</p>
          ) : (
            <ul className="reports-page__list">
              {shown.map((master) => (
                <li key={master.id}>
                  <CaseCard
                    master={master}
                    statuses={orderedStatuses}
                    category={categories.get(master.report_category_id)}
                    powers={powers}
                    signedOut={session.status === "signed-out"}
                    onSignIn={onSignIn}
                    onChange={replaceMaster}
                    onRemoved={() => dropMaster(master.id)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

type CaseCardProps = {
  master: MasterReport;
  statuses: MasterReportStatus[];
  /** report_categories.name, or undefined while the list is unknown */
  category: string | undefined;
  powers: Powers;
  signedOut: boolean;
  onSignIn: () => void;
  onChange: (master: MasterReport) => void;
  onRemoved: () => void;
};

/**
 * One case: its badge, title and text, then for staff the status switch and
 * the removal with its confirmation, and the thread folded under it.
 */
function CaseCard({
  master,
  statuses,
  category,
  powers,
  signedOut,
  onSignIn,
  onChange,
  onRemoved,
}: CaseCardProps) {
  const t = useMessages().reports;
  const locale = useLocale();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const statusName =
    statuses.find((status) => status.id === master.status_id)?.name ?? null;
  const kind = category && isCategoryName(category) ? category : null;

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

  const setStatus = (statusId: number) =>
    run(async () => {
      onChange(
        await reportsApi.updateMasterReport(master.id, { status_id: statusId }),
      );
    });

  const remove = () =>
    run(async () => {
      await reportsApi.removeMaster(master.id);
      onRemoved();
    });

  return (
    <article className="reports-page__case" aria-labelledby={`${id}-title`}>
      <div className="reports-page__case-grid">
        <div className="reports-page__case-main">
          <header className="reports-page__case-head">
            <div className="reports-page__case-meta">
              <StatusBadge status={statusName} />
              {kind && (
                <span className="reports-page__kind">{t.kinds[kind]}</span>
              )}
              <span className="reports-page__when">
                <time dateTime={master.created_at}>
                  {new Intl.DateTimeFormat(locale, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(master.created_at))}
                </time>
                {" · "}
                {t.reportCount(master.report_count)}
              </span>
            </div>
            <h2 id={`${id}-title`} className="reports-page__case-title">
              {master.title}
            </h2>
            <p className="reports-page__case-text">{master.description}</p>
          </header>

          {/* the institution's answer, shown the way the map's sheet shows it */}
          {master.response && (
            <aside
              className="reports-page__response"
              aria-label={t.officialResponse}
            >
              <span className="reports-page__response-label">
                {t.officialResponse}
              </span>
              <p className="reports-page__response-text">{master.response}</p>
            </aside>
          )}

          {powers.staff && (
            <div className="reports-page__actions">
              <div
                className="reports-page__switch"
                role="group"
                aria-label={t.setStatus}
              >
                {statuses.map((status) => (
                  <button
                    key={status.id}
                    type="button"
                    className="reports-page__tab"
                    aria-pressed={status.id === master.status_id}
                    disabled={busy}
                    onClick={() => {
                      if (status.id !== master.status_id)
                        void setStatus(status.id);
                    }}
                  >
                    {statusLabel(status.name, t)}
                  </button>
                ))}
              </div>

              {powers.admin &&
                (confirming ? (
                  <div className="reports-page__confirm">
                    <span className="reports-page__hint">{t.removeHint}</span>
                    <button
                      type="button"
                      className="reports-page__button"
                      disabled={busy}
                      onClick={() => setConfirming(false)}
                    >
                      {t.cancel}
                    </button>
                    <button
                      type="button"
                      className="reports-page__button reports-page__button--danger"
                      disabled={busy}
                      onClick={() => void remove()}
                    >
                      {busy ? t.removing : t.confirmRemove}
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="reports-page__button reports-page__button--danger"
                    disabled={busy}
                    onClick={() => setConfirming(true)}
                  >
                    {t.remove}
                  </button>
                ))}
            </div>
          )}

          {error && (
            <p className="reports-page__error" role="alert">
              {error}
            </p>
          )}
        </div>

        <CaseMedia
          master={master}
          kind={kind}
          powers={powers}
          signedOut={signedOut}
          onSignIn={onSignIn}
          onChange={onChange}
        />
      </div>

      <Thread
        masterId={master.id}
        powers={powers}
        signedOut={signedOut}
        onSignIn={onSignIn}
      />
    </article>
  );
}

type CaseMediaProps = {
  master: MasterReport;
  /** the case's category, or null while the list is unknown */
  kind: ReportCategoryName | null;
  powers: Powers;
  signedOut: boolean;
  onSignIn: () => void;
  onChange: (master: MasterReport) => void;
};

/**
 * The case's picture, which on a wide screen stands to the right of its text:
 * the earliest photo among its filings; a photo a resident offered, under a
 * question mark, which whoever filed the case takes or turns down here; or,
 * for a case with neither, the drafting frame with the way to offer one.
 */
function CaseMedia({
  master,
  kind,
  powers,
  signedOut,
  onSignIn,
  onChange,
}: CaseMediaProps) {
  const t = useMessages().reports;
  const [offering, setOffering] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (master.photo_url) {
    return (
      <figure className="reports-page__media">
        <img
          className="reports-page__photo"
          src={reportsApi.photoUrl({ url: master.photo_url })}
          alt={t.photoOf(master.title)}
          loading="lazy"
        />
      </figure>
    );
  }

  // the case is read again after a decision, so a taken photo takes the
  // question mark's place
  const reload = async () => onChange(await reportsApi.masterReport(master.id));

  const decide = async (approve: boolean) => {
    if (!master.pending_photo_id || deciding) return;
    setDeciding(true);
    setError(null);
    try {
      if (approve) {
        await photoProposalsApi.approve(master.pending_photo_id);
      } else {
        await photoProposalsApi.reject(master.pending_photo_id);
      }
      await reload();
    } catch (error) {
      setError(errorText(error, t));
    } finally {
      setDeciding(false);
    }
  };

  const waiting = master.pending_photo_url;
  // whoever filed the case decides about its photo, and so may an admin
  const decides =
    powers.admin || (powers.me !== null && powers.me === master.author_id);

  return (
    <div className="reports-page__media">
      {waiting ? (
        <figure className="reports-page__waiting">
          <img
            className="reports-page__photo reports-page__photo--pending"
            src={photoProposalsApi.photoUrl(waiting)}
            alt={t.pendingPhotoAlt(master.title)}
            loading="lazy"
          />
          {/* the mark rides the picture's top-left corner, clear of the
              decision under it */}
          <figcaption
            className="reports-page__photo-mark"
            title={t.pendingPhotoHint}
          >
            <span aria-hidden="true">?</span> {t.pendingPhoto}
          </figcaption>
          {/* only the resident who filed the case settles it */}
          {decides && (
            <div className="reports-page__photo-actions">
              <button
                type="button"
                className="reports-page__button reports-page__button--primary reports-page__button--compact"
                disabled={deciding}
                onClick={() => void decide(true)}
              >
                {deciding ? t.deciding : t.usePhoto}
              </button>
              <button
                type="button"
                className="reports-page__button reports-page__button--compact"
                disabled={deciding}
                onClick={() => void decide(false)}
              >
                {t.turnDownPhoto}
              </button>
            </div>
          )}
        </figure>
      ) : (
        <div className="reports-page__photo reports-page__photo--empty">
          {/* The pictogram is the way to offer a photo. While the session is
              still being restored neither answer applies, so it stays a drawing. */}
          {powers.me !== null || signedOut ? (
            <button
              type="button"
              className="reports-page__photo-glyph reports-page__photo-glyph--action"
              onClick={() => {
                if (powers.me) setOffering(true);
                else onSignIn();
              }}
            >
              <span aria-hidden="true">{kind ? KIND_GLYPHS[kind] : "?"}</span>
              <span className="visually-hidden">
                {powers.me ? t.proposePhoto : t.signInToProposePhoto}
              </span>
            </button>
          ) : (
            <span className="reports-page__photo-glyph" aria-hidden="true">
              {kind ? KIND_GLYPHS[kind] : "?"}
            </span>
          )}
          <span className="reports-page__photo-text">
            {powers.me !== null || signedOut ? t.proposePhoto : t.noPhoto}
          </span>
        </div>
      )}

      {error && (
        <p className="reports-page__error" role="alert">
          {error}
        </p>
      )}

      {offering && (
        <PhotoProposalDialog
          onClose={() => setOffering(false)}
          onSubmit={async (photo) => {
            await photoProposalsApi.offer(master.id, photo);
            await reload();
          }}
        />
      )}
    </div>
  );
}

type ThreadProps = {
  masterId: string;
  powers: Powers;
  signedOut: boolean;
  onSignIn: () => void;
};

/**
 * The case's discussion, loaded when unfolded: every comment, the official
 * ones marked, a delete button on the ones the viewer may remove, and a
 * compose box. Staff post as official unless unticked.
 */
function Thread({ masterId, powers, signedOut, onSignIn }: ThreadProps) {
  const t = useMessages().reports;
  const locale = useLocale();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [comments, setComments] = useState<MasterReportComment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [highlighted, setHighlighted] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || comments !== null) return;
    const controller = new AbortController();
    const { signal } = controller;
    reportsApi.comments(masterId, signal).then(
      (page) => {
        if (!signal.aborted) setComments(page.items);
      },
      (error) => {
        if (!signal.aborted) setError(errorText(error, t));
      },
    );
    return () => controller.abort();
    // the strings only matter for the fallback message
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, comments, masterId]);

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

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    void run(async () => {
      const comment = await reportsApi.addComment(
        masterId,
        content,
        powers.staff && highlighted,
      );
      setComments((current) => [...(current ?? []), comment]);
      setDraft("");
    });
  };

  const remove = (commentId: string) =>
    run(async () => {
      await reportsApi.deleteComment(commentId);
      setComments(
        (current) =>
          current?.filter((comment) => comment.id !== commentId) ?? null,
      );
    });

  const format = (iso: string) =>
    new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));

  return (
    <section className="reports-page__thread" aria-labelledby={`${id}-label`}>
      <button
        type="button"
        id={`${id}-label`}
        className="reports-page__fold"
        aria-expanded={open}
        aria-controls={`${id}-body`}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="reports-page__caret" aria-hidden="true" />
        {open ? t.hideComments : t.showComments}
        {comments && ` (${comments.length})`}
      </button>

      {open && (
        <div id={`${id}-body`} className="reports-page__thread-body">
          {comments === null && !error ? (
            <p className="reports-page__hint">{t.loadingComments}</p>
          ) : comments && comments.length === 0 ? (
            <p className="reports-page__hint">{t.noComments}</p>
          ) : (
            comments && (
              <ul className="reports-page__comments">
                {comments.map((comment) => {
                  const mine = comment.user_id === powers.me;
                  return (
                    <li
                      key={comment.id}
                      className={
                        comment.highlighted
                          ? "reports-page__comment reports-page__comment--official"
                          : "reports-page__comment"
                      }
                    >
                      <div className="reports-page__comment-head">
                        <span className="reports-page__author">
                          {mine
                            ? t.you
                            : comment.highlighted
                              ? t.office
                              : t.resident}
                          {comment.highlighted && (
                            <span className="reports-page__official">
                              {t.official}
                            </span>
                          )}
                        </span>
                        <time
                          className="reports-page__when"
                          dateTime={comment.created_at}
                        >
                          {format(comment.created_at)}
                        </time>
                      </div>
                      <p className="reports-page__comment-text">
                        {comment.content}
                      </p>
                      {/* the api lets the author and staff delete a comment */}
                      {(mine || powers.staff) && (
                        <button
                          type="button"
                          className="reports-page__link-button"
                          disabled={busy}
                          onClick={() => void remove(comment.id)}
                        >
                          {t.deleteComment}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )
          )}

          {error && (
            <p className="reports-page__error" role="alert">
              {error}
            </p>
          )}

          {powers.me ? (
            <form className="reports-page__compose" onSubmit={submit}>
              <label className="visually-hidden" htmlFor={`${id}-draft`}>
                {t.composeLabel}
              </label>
              <textarea
                id={`${id}-draft`}
                className="reports-page__input reports-page__textarea"
                rows={2}
                disabled={busy}
                placeholder={t.composePlaceholder}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
              />
              <div className="reports-page__compose-row">
                {powers.staff ? (
                  <label className="reports-page__check">
                    <input
                      type="checkbox"
                      checked={highlighted}
                      disabled={busy}
                      onChange={(event) => setHighlighted(event.target.checked)}
                    />
                    {t.highlight}
                  </label>
                ) : (
                  <span />
                )}
                <button
                  type="submit"
                  className="reports-page__button reports-page__button--primary"
                  disabled={!draft.trim() || busy}
                >
                  {busy ? t.posting : t.post}
                </button>
              </div>
            </form>
          ) : (
            signedOut && (
              <button
                type="button"
                className="reports-page__button"
                onClick={onSignIn}
              >
                {t.signInToComment}
              </button>
            )
          )}
        </div>
      )}
    </section>
  );
}
