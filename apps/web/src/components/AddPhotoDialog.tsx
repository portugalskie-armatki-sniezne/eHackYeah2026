import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useMessages } from "../i18n/locale";
import "./PinDialog.css";
import "./PhotoReportDialog.css";

type AddPhotoDialogProps = {
  onClose: () => void;
  /**
   * adds the chosen photo to the case. The api serves the saved file at
   * once, so the sheet reads the photo back from there rather than from here.
   */
  onSubmit: (photo: File) => Promise<void>;
};

/**
 * the sheet that adds a photo to a case: pick a picture and save it,
 * and it appears with the case immediately.
 * It shares the pin sheet's look; Escape and Cancel drop the choice.
 */
export default function AddPhotoDialog({
  onClose,
  onSubmit,
}: AddPhotoDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);
  const id = useId();
  const t = useMessages().addPhoto;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  // the preview belongs to this sheet and goes when the sheet does
  useEffect(
    () => () => {
      if (photoUrl) {
        URL.revokeObjectURL(photoUrl);
      }
    },
    [photoUrl],
  );

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setPhoto(file);
    setPhotoUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return file ? URL.createObjectURL(file) : null;
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!photo || savingRef.current) {
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await onSubmit(photo);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.saveFailed);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

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

        {photoUrl ? (
          <img
            className="photo-report__preview"
            src={photoUrl}
            alt={t.photoAlt}
          />
        ) : (
          <div className="pin-dialog__image">
            <span className="pin-dialog__placeholder" aria-hidden="true">
              {t.none}
            </span>
          </div>
        )}

        <div className="pin-dialog__field">
          <span className="pin-dialog__label" id={`${id}-photo-label`}>
            {t.photo}
          </span>
          <label className="pin-dialog__button pin-dialog__file">
            {photo ? t.change : t.choose}
            <input
              className="visually-hidden"
              type="file"
              name="photo"
              accept="image/jpeg,image/png,image/webp"
              disabled={saving}
              aria-labelledby={`${id}-photo-label`}
              onChange={handleChange}
            />
          </label>
        </div>

        <footer className="pin-dialog__actions">
          <button
            type="button"
            className="pin-dialog__button"
            onClick={() => dialogRef.current?.close()}
            disabled={saving}
          >
            {t.cancel}
          </button>
          <button
            type="submit"
            className="pin-dialog__button pin-dialog__button--primary"
            disabled={!photo || saving}
          >
            {saving ? t.sending : t.send}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
