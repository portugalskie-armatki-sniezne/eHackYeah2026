import { useEffect, useId, useRef } from "react";
import { useMessages } from "../i18n/locale";
import "./AuthDialog.css";

type SignOutDialogProps = {
  onClose: () => void;
  onConfirm: () => void;
};

/**
 * Asks before signing out. It shares the account sheet's look; Escape and
 * Cancel keep the session.
 */
export default function SignOutDialog({
  onClose,
  onConfirm,
}: SignOutDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const id = useId();
  const t = useMessages().signOut;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className="auth-dialog"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-text`}
      onClose={onClose}
    >
      <div className="auth-dialog__form">
        <header className="auth-dialog__header">
          <h2 id={`${id}-title`} className="auth-dialog__title">
            {t.title}
          </h2>
        </header>

        <p id={`${id}-text`} className="auth-dialog__text">
          {t.question}
        </p>

        <footer className="auth-dialog__actions">
          <button
            type="button"
            className="auth-dialog__button"
            autoFocus
            onClick={() => dialogRef.current?.close()}
          >
            {t.cancel}
          </button>
          <button
            type="button"
            className="auth-dialog__button auth-dialog__button--primary"
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            {t.confirm}
          </button>
        </footer>
      </div>
    </dialog>
  );
}
