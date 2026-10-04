import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { letterFor, type ReportLetter } from "../api/letters";
import {
  reportsApi,
  type MasterReportComment,
  type MasterReportDetail,
  type ReportCategoryName,
} from "../api/reports";
import { useSession } from "../api/session";
import StatusBadge from "./StatusBadge";
import MarkerRecipient from "./MarkerRecipient";
import "./MarkerDialog.css";

type MarkerDialogProps = {
  /** the master report the clicked pin stands for */
  masterId: string;
  /** picks the post's avatar glyph, as it picks the pin's */
  category: ReportCategoryName;
  onClose: () => void;
  /** Called when a signed-out visitor tries to comment. */
  onSignInRequired: () => void;
};

// everything the sheet shows, loaded together so it opens filled in
type Sheet = {
  master: MasterReportDetail;
  /** master_report_statuses.name, or null when the id is not in the list */
  status: string | null;
  letter: ReportLetter;
};

const KIND_LABELS: Record<ReportCategoryName, string> = {
  issue: "Fault report",
  improvement: "Improvement idea",
};

// the pin's pictogram in text: "!" for a fault, "+" for an improvement
const KIND_GLYPHS: Record<ReportCategoryName, string> = {
  issue: "!",
  improvement: "+",
};

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["week", 7 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
];

// "3 hours ago" rather than a timestamp, the way a feed dates its posts
function timeAgo(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  for (const [unit, span] of UNITS) {
    if (Math.abs(seconds) >= span) {
      return RELATIVE.format(-Math.round(seconds / span), unit);
    }
  }
  return "just now";
}

const ROPS_PATTERN =
  /\[?Inicjatywa oparta na innowacji ROPS:\s*([^\n()[\]]+?)(?:\s*\((https?:\/\/[^\s)]+)\)|\s*\n\s*(https?:\/\/[^\s)]+))\]?/i;

type ParsedBody = {
  cleanText: string;
  ropsInnovation: {
    title: string;
    url: string;
  } | null;
};

function parseRopsInnovation(body: string): ParsedBody {
  const match = ROPS_PATTERN.exec(body);
  if (!match) {
    return { cleanText: body, ropsInnovation: null };
  }
  const title = match[1]?.trim() ?? "";
  const rawUrl = match[2] || match[3] || "";
  const url = rawUrl.replace(/[)\]]+$/, "");
  const cleanText = body.replace(match[0], "").trim();
  return {
    cleanText,
    ropsInnovation: { title, url },
  };
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function renderTextWithLinks(text: string) {
  const urlRegex = /(https?:\/\/[^\s)\]]+)/g;
  const parts = text.split(urlRegex);
  return parts.map((part, index) =>
    urlRegex.test(part) ? (
      <a
        key={index}
        href={part}
        target="_blank"
        rel="noopener noreferrer"
        className="marker-dialog__link"
      >
        {part}
      </a>
    ) : (
      part
    ),
  );
}

/**
 * The post a pin opens: the filing's photos, its title and letter to the
 * responsible body, its status, and the discussion under it. A native dialog
 * like the marker sheet, so Escape and the corner button are the same way out.
 */
export default function MarkerDialog({
  masterId,
  category,
  onClose,
  onSignInRequired,
}: MarkerDialogProps) {
  const session = useSession();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const id = useId();
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [comments, setComments] = useState<MasterReportComment[]>([]);
  const [error, setError] = useState<string | null>(null);
  // which of the post's photos fills the frame
  const [photoIndex, setPhotoIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const postingRef = useRef(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const [master, statuses, discussion] = await Promise.all([
          reportsApi.masterReport(masterId, signal),
          reportsApi.statuses(signal),
          reportsApi.comments(masterId, signal),
        ]);
        const letter = await letterFor(master, signal);
        if (signal.aborted) return;
        setSheet({
          master,
          status:
            statuses.find((status) => status.id === master.status_id)?.name ??
            null,
          letter,
        });
        setComments(discussion.items);
      } catch (error) {
        if (signal.aborted) return;
        setError(
          error instanceof Error ? error.message : "Could not load the report.",
        );
      }
    }
    void load();
    return () => controller.abort();
  }, [masterId]);

  const replaceComment = (next: MasterReportComment) =>
    setComments((current) =>
      current.map((comment) => (comment.id === next.id ? next : comment)),
    );

  const handleLike = async (comment: MasterReportComment) => {
    if (session.status !== "signed-in") {
      onSignInRequired();
      return;
    }
    try {
      replaceComment(
        comment.liked_by_me
          ? await reportsApi.unlikeComment(comment.id)
          : await reportsApi.likeComment(comment.id),
      );
    } catch (error) {
      setCommentError(
        error instanceof Error ? error.message : "Could not save the like.",
      );
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || postingRef.current) {
      return;
    }
    postingRef.current = true;
    setPosting(true);
    setCommentError(null);
    try {
      const comment = await reportsApi.addComment(masterId, content);
      setComments((current) => [...current, comment]);
      setDraft("");
    } catch (error) {
      setCommentError(
        error instanceof Error ? error.message : "Could not post the comment.",
      );
    } finally {
      postingRef.current = false;
      setPosting(false);
    }
  };

  const me = session.status === "signed-in" ? session.user.id : null;
  const myInitial =
    session.status === "signed-in"
      ? (session.user.first_name[0] ?? "?").toUpperCase()
      : "?";
  const master = sheet?.master;
  const photos = master?.photos ?? [];
  const photo = photos[Math.min(photoIndex, photos.length - 1)];
  const letter = sheet?.letter;

  return (
    <dialog
      ref={dialogRef}
      className="marker-dialog"
      aria-labelledby={`${id}-title`}
      onClose={onClose}
    >
      <article className="marker-dialog__post">
        <button
          type="button"
          className="marker-dialog__close"
          onClick={() => dialogRef.current?.close()}
        >
          <span aria-hidden="true">&times;</span>
          <span className="visually-hidden">Close</span>
        </button>

        {/* The photo leads, the way a post does; a filing without one gets the
            drafting grid the marker sheet shows before an image is chosen. */}
        <figure className="marker-dialog__figure">
          {photo ? (
            <img
              className="marker-dialog__photo"
              src={reportsApi.photoUrl(photo)}
              alt={master ? `Photo of: ${master.title}` : "Report photo"}
            />
          ) : (
            <div className="marker-dialog__photo marker-dialog__photo--empty">
              <span
                className="marker-dialog__placeholder-glyph"
                aria-hidden="true"
              >
                {KIND_GLYPHS[category]}
              </span>
              {!sheet && !error && (
                <span className="marker-dialog__placeholder-text">
                  Loading...
                </span>
              )}
              {sheet && (
                <span className="marker-dialog__placeholder-text">
                  No photo yet
                </span>
              )}
            </div>
          )}
          {sheet && (
            <figcaption className="marker-dialog__badge">
              <StatusBadge status={sheet.status} />
            </figcaption>
          )}
        </figure>

        {photos.length > 1 && (
          <div
            className="marker-dialog__strip"
            role="group"
            aria-label="Photos"
          >
            {photos.map((item, index) => (
              <button
                key={item.id}
                type="button"
                className="marker-dialog__thumb"
                aria-pressed={index === photoIndex}
                onClick={() => setPhotoIndex(index)}
              >
                <img src={reportsApi.photoUrl(item)} alt="" />
                <span className="visually-hidden">
                  Photo {index + 1} of {photos.length}
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="marker-dialog__body">
          <header className="marker-dialog__byline">
            <span
              className="marker-dialog__avatar marker-dialog__avatar--post"
              aria-hidden="true"
            >
              {KIND_GLYPHS[category]}
            </span>
            <div className="marker-dialog__who">
              <span className="marker-dialog__kind">
                {KIND_LABELS[category]}
              </span>
              {master && (
                <span className="marker-dialog__when">
                  <time
                    dateTime={master.created_at}
                    title={formatDate(master.created_at)}
                  >
                    {timeAgo(master.created_at)}
                  </time>
                  {" · "}
                  {master.report_count === 1
                    ? "1 report"
                    : `${master.report_count} reports`}
                </span>
              )}
            </div>
          </header>

          <h2 id={`${id}-title`} className="marker-dialog__title">
            {master ? master.title : error ? "Report" : "Loading report"}
          </h2>

          {error && (
            <p className="marker-dialog__error" role="alert">
              {error}
            </p>
          )}

          {letter &&
            master &&
            (() => {
              const { cleanText, ropsInnovation } = parseRopsInnovation(
                letter.body,
              );
              return (
                <div className="marker-dialog__letter">
                  <dl className="marker-dialog__envelope">
                    <dt>To</dt>
                    <dd>
                      <MarkerRecipient
                        master={master}
                        letter={letter}
                        onSignInRequired={onSignInRequired}
                      />
                    </dd>
                    <dt>Subject</dt>
                    <dd>{letter.subject}</dd>
                  </dl>
                  {cleanText && (
                    <p className="marker-dialog__text">
                      {renderTextWithLinks(cleanText)}
                    </p>
                  )}
                  {ropsInnovation && (
                    <aside
                      className="marker-dialog__rops-box"
                      aria-label="Innowacja ROPS"
                    >
                      <div className="marker-dialog__rops-header">
                        <span className="marker-dialog__rops-badge">
                          Innowacja ROPS
                        </span>
                      </div>
                      <div className="marker-dialog__rops-content">
                        <strong className="marker-dialog__rops-title">
                          {ropsInnovation.title}
                        </strong>
                        <a
                          href={ropsInnovation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="marker-dialog__rops-link"
                        >
                          Zobacz model innowacji na rops.krakow.pl &rarr;
                        </a>
                      </div>
                    </aside>
                  )}
                </div>
              );
            })()}

          {sheet && master?.response && (
            <aside
              className="marker-dialog__response"
              aria-label="Official response"
            >
              <span className="marker-dialog__response-label">
                Official response
              </span>
              <p className="marker-dialog__text">
                {renderTextWithLinks(master.response)}
              </p>
            </aside>
          )}
        </div>

        {sheet && (
          <section
            className="marker-dialog__comments"
            aria-labelledby={`${id}-comments`}
          >
            <h3 id={`${id}-comments`} className="marker-dialog__label">
              {comments.length === 0
                ? "Comments"
                : comments.length === 1
                  ? "1 comment"
                  : `${comments.length} comments`}
            </h3>
            {comments.length === 0 ? (
              <p className="marker-dialog__hint">
                Nobody has weighed in yet. Be the first.
              </p>
            ) : (
              <ul className="marker-dialog__feed">
                {comments.map((comment) => {
                  const mine = comment.user_id === me;
                  return (
                    <li key={comment.id} className="marker-dialog__comment">
                      <span
                        className={
                          mine
                            ? "marker-dialog__avatar marker-dialog__avatar--me"
                            : "marker-dialog__avatar"
                        }
                        aria-hidden="true"
                      >
                        {mine ? myInitial : "R"}
                      </span>
                      <div className="marker-dialog__bubble">
                        <div className="marker-dialog__comment-head">
                          <span className="marker-dialog__author">
                            {mine ? "You" : "Resident"}
                          </span>
                          <time
                            className="marker-dialog__when"
                            dateTime={comment.created_at}
                            title={formatDate(comment.created_at)}
                          >
                            {timeAgo(comment.created_at)}
                          </time>
                        </div>
                        <p className="marker-dialog__comment-text">
                          {comment.content}
                        </p>
                        <button
                          type="button"
                          className="marker-dialog__like"
                          aria-pressed={comment.liked_by_me}
                          onClick={() => void handleLike(comment)}
                        >
                          <span aria-hidden="true">
                            {comment.liked_by_me ? "♥" : "♡"}
                          </span>{" "}
                          {comment.like_count}
                          <span className="visually-hidden">
                            {comment.liked_by_me
                              ? " likes, unlike"
                              : " likes, like"}
                          </span>
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            {commentError && (
              <p className="marker-dialog__error" role="alert">
                {commentError}
              </p>
            )}

            {session.status === "signed-in" ? (
              <form className="marker-dialog__compose" onSubmit={handleSubmit}>
                <span
                  className="marker-dialog__avatar marker-dialog__avatar--me"
                  aria-hidden="true"
                >
                  {myInitial}
                </span>
                <label className="visually-hidden" htmlFor={`${id}-comment`}>
                  New comment
                </label>
                <textarea
                  id={`${id}-comment`}
                  className="marker-dialog__textarea"
                  rows={1}
                  disabled={posting}
                  placeholder="Write a comment..."
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <button
                  type="submit"
                  className="marker-dialog__button marker-dialog__button--primary"
                  disabled={!draft.trim() || posting}
                >
                  {posting ? "Posting..." : "Post"}
                </button>
              </form>
            ) : (
              session.status === "signed-out" && (
                <button
                  type="button"
                  className="marker-dialog__button"
                  onClick={onSignInRequired}
                >
                  Sign in to comment
                </button>
              )
            )}
          </section>
        )}
      </article>
    </dialog>
  );
}
