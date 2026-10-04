import { useEffect, useState } from "react";
import {
  letterMailto,
  recommendedRecipient,
  type LetterRecipient,
  type ReportLetter,
} from "../api/letters";
import type { MasterReportDetail } from "../api/reports";
import { useSession } from "../api/session";

function Recipient({
  recipient,
  letter,
}: {
  recipient: LetterRecipient;
  letter: ReportLetter;
}) {
  return (
    <>
      <span className="marker-dialog__recipient">{recipient.name}</span>
      {recipient.email ? (
        <a
          className="marker-dialog__link"
          href={letterMailto(recipient, letter)}
        >
          {recipient.email}
        </a>
      ) : (
        <span className="marker-dialog__hint">no email on record</span>
      )}
      {recipient.contact && (
        <>
          <a className="marker-dialog__link" href={recipient.contact.url}>
            Contact institution
          </a>
          {recipient.contact.description && (
            <span className="marker-dialog__hint">
              {recipient.contact.description}
            </span>
          )}
        </>
      )}
    </>
  );
}

type RecommendationState =
  | { status: "loading" }
  | { status: "ready"; recipient: LetterRecipient | null }
  | { status: "error"; message: string };

function RecommendedRecipient({
  master,
  letter,
}: {
  master: MasterReportDetail;
  letter: ReportLetter;
}) {
  const [state, setState] = useState<RecommendationState>({
    status: "loading",
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    void recommendedRecipient(master, signal).then(
      (recipient) => {
        if (!signal.aborted) setState({ status: "ready", recipient });
      },
      (error: unknown) => {
        if (!signal.aborted)
          setState({
            status: "error",
            message:
              error instanceof Error
                ? error.message
                : "Could not find a recipient.",
          });
      },
    );
    return () => controller.abort();
  }, [master, attempt]);

  if (state.status === "loading") {
    return (
      <span className="marker-dialog__hint" role="status">
        Finding a suggested recipient...
      </span>
    );
  }
  if (state.status === "error") {
    return (
      <>
        <span className="marker-dialog__hint" role="alert">
          Could not load the suggested recipient. {state.message}
        </span>
        <button
          type="button"
          className="marker-dialog__button"
          onClick={() => {
            setState({ status: "loading" });
            setAttempt((value) => value + 1);
          }}
        >
          Try again
        </button>
      </>
    );
  }
  if (!state.recipient) {
    return (
      <span className="marker-dialog__hint">
        No matching institution found.
      </span>
    );
  }
  return (
    <>
      <Recipient recipient={state.recipient} letter={letter} />
      <span className="marker-dialog__hint">
        Suggested recipient based on the report and location. Not assigned yet.
      </span>
    </>
  );
}

export default function MarkerRecipient({
  master,
  letter,
  onSignInRequired,
}: {
  master: MasterReportDetail;
  letter: ReportLetter;
  onSignInRequired: () => void;
}) {
  const session = useSession();
  if (letter.recipient)
    return <Recipient recipient={letter.recipient} letter={letter} />;
  if (session.status === "checking")
    return <span className="marker-dialog__hint">Checking sign-in...</span>;
  if (session.status === "signed-out") {
    return (
      <button
        type="button"
        className="marker-dialog__button"
        onClick={onSignInRequired}
      >
        Sign in to find a recipient
      </button>
    );
  }
  return (
    <RecommendedRecipient
      key={`${master.id}:${session.user.id}`}
      master={master}
      letter={letter}
    />
  );
}
