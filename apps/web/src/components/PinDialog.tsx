import {
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import "./PinDialog.css";

export type PinDraft = {
  description: string;
  image: File | null;
  /** Object URL for the chosen image, owned by the pin once added. */
  imageUrl: string | null;
};

type PinDialogProps = {
  lngLat: [number, number];
  onClose: () => void;
  onAdd: (draft: PinDraft) => Promise<void>;
};

function formatLngLat([lng, lat]: [number, number]): string {
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

/**
 * The sheet that opens when a pin is dropped: a description and an optional
 * photo. It is a native dialog, so focus stays inside it and Escape closes it
 * the same way the Close button does; the pin is only kept once "Add marker"
 * submits the form.
 */
export default function PinDialog({ lngLat, onClose, onAdd }: PinDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [description, setDescription] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);
  // the preview URL is handed to the pin on add, so it is only revoked here
  // when the sheet is closed without adding
  const addedRef = useRef(false);
  const id = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  useEffect(
    () => () => {
      if (!addedRef.current && imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    },
    [imageUrl],
  );

  const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setImage(file);
    setImageUrl(file ? URL.createObjectURL(file) : null);
  };

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
      await onAdd({ description: trimmed, image, imageUrl });
      addedRef.current = true;
      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Could not save the report.",
      );
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const canAdd = description.trim().length > 0;

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
      <form
        className="pin-dialog__form"
        method="dialog"
        onSubmit={handleSubmit}
      >
        <header className="pin-dialog__header">
          <h2 id={`${id}-title`} className="pin-dialog__title">
            New marker
          </h2>
          <p className="pin-dialog__coords">{formatLngLat(lngLat)}</p>
        </header>

        {error && <p role="alert">{error}</p>}

        <div className="pin-dialog__field">
          <label className="pin-dialog__label" htmlFor={`${id}-description`}>
            Description
          </label>
          <textarea
            id={`${id}-description`}
            className="pin-dialog__textarea"
            name="description"
            rows={4}
            required
            disabled={saving}
            placeholder="What is happening here?"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>

        <div className="pin-dialog__field">
          <span className="pin-dialog__label" id={`${id}-image-label`}>
            Image
          </span>
          <div className="pin-dialog__image">
            {imageUrl ? (
              <img
                className="pin-dialog__preview"
                src={imageUrl}
                alt={image?.name ?? "Chosen image"}
              />
            ) : (
              <span className="pin-dialog__placeholder" aria-hidden="true">
                No image
              </span>
            )}
            <label className="pin-dialog__button pin-dialog__file">
              {image ? "Change image" : "Choose image"}
              <input
                className="visually-hidden"
                type="file"
                name="image"
                accept="image/jpeg,image/png,image/webp"
                disabled={saving}
                aria-labelledby={`${id}-image-label`}
                onChange={handleImageChange}
              />
            </label>
          </div>
        </div>

        <footer className="pin-dialog__actions">
          <button
            type="button"
            className="pin-dialog__button"
            onClick={() => dialogRef.current?.close()}
            disabled={saving}
          >
            Close
          </button>
          <button
            type="submit"
            className="pin-dialog__button pin-dialog__button--primary"
            disabled={!canAdd || saving}
          >
            {saving ? "Saving..." : "Add marker"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
