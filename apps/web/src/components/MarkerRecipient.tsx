import { useEffect, useState } from "react";
import {
  letterMailto,
  recommendedRecipient,
  type LetterRecipient,
  type ReportLetter,
} from "../api/letters";
import type { MasterReportDetail } from "../api/reports";
import { useSession } from "../api/session";
import { useMessages } from "../i18n/locale";

function Recipient({
  recipient,
  letter,
}: {
  recipient: LetterRecipient;
  letter: ReportLetter;
}) {
  const t = useMessages().marker;
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
        <span className="marker-dialog__hint">{t.noEmail}</span>
      )}
      {recipient.contact && (
        <>
          <a className="marker-dialog__link" href={recipient.contact.url}>
            {t.contactInstitution}
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
  const t = useMessages().marker;
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
            message: error instanceof Error ? error.message : t.recipientFailed,
          });
      },
    );
    return () => controller.abort();
    // the fallback text is read once, when the lookup fails
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [master, attempt]);

  if (state.status === "loading") {
    return (
      <span className="marker-dialog__hint" role="status">
        {t.findingRecipient}
      </span>
    );
  }
  if (state.status === "error") {
    return (
      <>
        <span className="marker-dialog__hint" role="alert">
          {t.recipientLoadFailed} {state.message}
        </span>
        <button
          type="button"
          className="marker-dialog__button"
          onClick={() => {
            setState({ status: "loading" });
            setAttempt((value) => value + 1);
          }}
        >
          {t.tryAgain}
        </button>
      </>
    );
  }
  if (!state.recipient) {
    return <span className="marker-dialog__hint">{t.noInstitution}</span>;
  }
  return (
    <>
      <Recipient recipient={state.recipient} letter={letter} />
      <span className="marker-dialog__hint">{t.suggestedRecipient}</span>
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
  const t = useMessages().marker;
  if (letter.recipient)
    return <Recipient recipient={letter.recipient} letter={letter} />;
  if (session.status === "checking")
    return <span className="marker-dialog__hint">{t.checkingSignIn}</span>;
  if (session.status === "signed-out") {
    return (
      <button
        type="button"
        className="marker-dialog__button"
        onClick={onSignInRequired}
      >
        {t.signInToFindRecipient}
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
