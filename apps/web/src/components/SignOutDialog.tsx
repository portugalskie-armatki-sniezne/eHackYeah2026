import { useEffect, useId, useRef } from "react";
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
            Sign out
          </h2>
        </header>

        <p id={`${id}-text`} className="auth-dialog__text">
          Are you sure you want to sign out?
        </p>

        <footer className="auth-dialog__actions">
          <button
            type="button"
            className="auth-dialog__button"
            autoFocus
            onClick={() => dialogRef.current?.close()}
          >
            Cancel
          </button>
          <button
            type="button"
            className="auth-dialog__button auth-dialog__button--primary"
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            Sign out
          </button>
        </footer>
      </div>
    </dialog>
  );
}
