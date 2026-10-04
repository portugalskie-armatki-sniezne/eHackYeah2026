import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useMessages } from "../i18n/locale";
import "./PinDialog.css";
import "./PhotoReportDialog.css";

type PhotoReportDialogProps = {
  /** The photo just taken with the toolbar's "+" tile. */
  photo: File;
  onClose: () => void;
  /**
   * Files the photo under the description typed here. The preview URL goes
   * with it so the new pin can show the photo before the saved one is fetched.
   */
  onSubmit: (description: string, photoUrl: string) => Promise<void>;
};

/**
 * The sheet that opens on a phone once the camera returns, so the photo is
 * filed with a description rather than on its own. It shares the pin sheet's
 * look; Escape and Discard drop the photo.
 */
export default function PhotoReportDialog({
  photo,
  onClose,
  onSubmit,
}: PhotoReportDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  // made once for this photo, and handed to the pin when the report saves
  const [photoUrl] = useState(() => URL.createObjectURL(photo));
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);
  const sentRef = useRef(false);
  const id = useId();
  const t = useMessages().photoReport;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  // a discarded photo takes its preview with it; a sent one leaves it to the pin
  useEffect(
    () => () => {
      if (!sentRef.current) {
        URL.revokeObjectURL(photoUrl);
      }
    },
    [photoUrl],
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = description.trim();
    if (!trimmed || savingRef.current) {
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await onSubmit(trimmed, photoUrl);
      sentRef.current = true;
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.saveFailed);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const canSend = description.trim().length > 0;

  return (
    <dialog
      ref={dialogRef}
      className="pin-dialog"
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      onCancel={(event) => {
        if (savingRef.current) event.preventDefault();
      }}
    >
      <form className="pin-dialog__form" onSubmit={handleSubmit}>
        <header className="pin-dialog__header">
          <h2 id={`${id}-title`} className="pin-dialog__title">
            {t.title}
          </h2>
          <p className="pin-dialog__coords">{t.hint}</p>
        </header>

        {error && (
          <p className="pin-dialog__alert" role="alert">
            {error}
          </p>
        )}

        <img
          className="photo-report__preview"
          src={photoUrl}
          alt={t.photoAlt}
        />

        <div className="pin-dialog__field">
          <label className="pin-dialog__label" htmlFor={`${id}-description`}>
            {t.description}
          </label>
          <textarea
            id={`${id}-description`}
            className="pin-dialog__textarea"
            name="description"
            rows={3}
            required
            disabled={saving}
            placeholder={t.descriptionPlaceholder}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>

        <footer className="pin-dialog__actions">
          <button
            type="button"
            className="pin-dialog__button"
            onClick={() => dialogRef.current?.close()}
            disabled={saving}
          >
            {t.discard}
          </button>
          <button
            type="submit"
            className="pin-dialog__button pin-dialog__button--primary"
            disabled={!canSend || saving}
          >
            {saving ? t.saving : t.send}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
