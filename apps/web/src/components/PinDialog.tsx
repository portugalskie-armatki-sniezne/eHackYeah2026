import {
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { projectsApi, type ProjectSearchResult } from "../api/projects";
import type { ReportCategoryName } from "../api/reports";
import { useMessages } from "../i18n/locale";
import "./PinDialog.css";

export type PinDraft = {
  description: string;
  image: File | null;
  /** Object URL for the chosen image, owned by the pin once added. */
  imageUrl: string | null;
  category?: ReportCategoryName;
  projectSlug?: string;
};

type PinDialogProps = {
  lngLat: [number, number];
  onClose: () => void;
  onAdd: (draft: PinDraft) => Promise<void>;
};

function formatLngLat([lng, lat]: [number, number]): string {
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

const SIMILARITY_THRESHOLD = 0.55;

/**
 * The sheet that opens when a pin is dropped. Supports two modes:
 * - "issue": standard fault / communal issue report with description and optional photo.
 * - "initiative": civic improvement initiative with vector similarity check against ROPS projects.
 */
export default function PinDialog({ lngLat, onClose, onAdd }: PinDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [activeTab, setActiveTab] = useState<"issue" | "initiative">("issue");
  const [description, setDescription] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [checkingSimilarity, setCheckingSimilarity] = useState(false);
  const [detectedMatch, setDetectedMatch] =
    useState<ProjectSearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);
  const addedRef = useRef(false);
  const id = useId();
  const t = useMessages().pin;

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

  const executeAdd = async (
    finalDescription: string,
    category: ReportCategoryName,
    img: File | null,
    imgUrl: string | null,
    projectSlug?: string,
  ) => {
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await onAdd({
        description: finalDescription,
        image: img,
        imageUrl: imgUrl,
        category,
        projectSlug,
      });
      addedRef.current = true;
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.saveFailed);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const handleSubmitIssue = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = description.trim();
    if (!trimmed || savingRef.current) return;
    await executeAdd(trimmed, "issue", image, imageUrl);
  };

  const handleInitiativeSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = description.trim();
    if (!trimmed || savingRef.current || checkingSimilarity) return;

    setCheckingSimilarity(true);
    setError(null);
    try {
      const results = await projectsApi.search(trimmed, { limit: 1 });
      const topMatch = results[0];
      if (topMatch && topMatch.score > SIMILARITY_THRESHOLD) {
        setDetectedMatch(topMatch);
      } else {
        await executeAdd(trimmed, "improvement", null, null);
      }
    } catch {
      // fallback: if vector search is temporarily unreachable, still save the initiative
      await executeAdd(trimmed, "improvement", null, null);
    } finally {
      setCheckingSimilarity(false);
    }
  };

  const handleLinkToMatch = async () => {
    if (!detectedMatch) return;
    const trimmed = description.trim();
    const finalDesc = `${trimmed}\n\nInicjatywa oparta na innowacji ROPS: ${detectedMatch.title}\n${detectedMatch.url}`;
    await executeAdd(finalDesc, "improvement", null, null, detectedMatch.slug);
  };

  const handleSaveAsNewInitiative = async () => {
    const trimmed = description.trim();
    await executeAdd(trimmed, "improvement", null, null);
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
      <div className="pin-dialog__tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "issue"}
          className={`pin-dialog__tab ${activeTab === "issue" ? "pin-dialog__tab--active" : ""}`}
          onClick={() => {
            setActiveTab("issue");
            setDetectedMatch(null);
            setError(null);
          }}
          disabled={saving || checkingSimilarity}
        >
          {t.issueTab}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "initiative"}
          className={`pin-dialog__tab ${activeTab === "initiative" ? "pin-dialog__tab--active" : ""}`}
          onClick={() => {
            setActiveTab("initiative");
            setDetectedMatch(null);
            setError(null);
          }}
          disabled={saving || checkingSimilarity}
        >
          {t.initiativeTab}
        </button>
      </div>

      {activeTab === "issue" ? (
        <form className="pin-dialog__form" onSubmit={handleSubmitIssue}>
          <header className="pin-dialog__header">
            <h2 id={`${id}-title`} className="pin-dialog__title">
              {t.newMarker}
            </h2>
            <p className="pin-dialog__coords">{formatLngLat(lngLat)}</p>
          </header>

          {error && (
            <p className="pin-dialog__alert" role="alert">
              {error}
            </p>
          )}

          <div className="pin-dialog__field">
            <label className="pin-dialog__label" htmlFor={`${id}-description`}>
              {t.description}
            </label>
            <textarea
              id={`${id}-description`}
              className="pin-dialog__textarea"
              name="description"
              rows={4}
              required
              disabled={saving}
              placeholder={t.descriptionPlaceholder}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <div className="pin-dialog__field">
            <span className="pin-dialog__label" id={`${id}-image-label`}>
              {t.image}
            </span>
            <div className="pin-dialog__image">
              {imageUrl ? (
                <img
                  className="pin-dialog__preview"
                  src={imageUrl}
                  alt={image?.name ?? t.chosenImage}
                />
              ) : (
                <span className="pin-dialog__placeholder" aria-hidden="true">
                  {t.noImage}
                </span>
              )}
              <label className="pin-dialog__button pin-dialog__file">
                {image ? t.changeImage : t.chooseImage}
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
              {t.close}
            </button>
            <button
              type="submit"
              className="pin-dialog__button pin-dialog__button--primary"
              disabled={!canAdd || saving}
            >
              {saving ? t.saving : t.addMarker}
            </button>
          </footer>
        </form>
      ) : (
        <form className="pin-dialog__form" onSubmit={handleInitiativeSubmit}>
          <header className="pin-dialog__header">
            <h2 id={`${id}-title`} className="pin-dialog__title">
              {t.initiativeTab}
            </h2>
            <p className="pin-dialog__coords">{formatLngLat(lngLat)}</p>
          </header>

          {error && (
            <p className="pin-dialog__alert" role="alert">
              {error}
            </p>
          )}

          {detectedMatch ? (
            <div className="pin-dialog__match-box">
              <div className="pin-dialog__match-badge">
                {t.matchFound(Math.round(detectedMatch.score * 100))}
              </div>
              <h3 className="pin-dialog__match-title">{detectedMatch.title}</h3>
              <span className="pin-dialog__match-category">
                {detectedMatch.category}
              </span>
              <p className="pin-dialog__match-desc">
                {detectedMatch.matched_snippet ||
                  detectedMatch.description ||
                  detectedMatch.summary}
              </p>
              <div className="pin-dialog__match-actions">
                <button
                  type="button"
                  className="pin-dialog__button pin-dialog__button--primary"
                  onClick={handleLinkToMatch}
                  disabled={saving}
                >
                  {saving ? t.saving : t.useProject}
                </button>
                <button
                  type="button"
                  className="pin-dialog__button"
                  onClick={handleSaveAsNewInitiative}
                  disabled={saving}
                >
                  {saving ? t.saving : t.saveAsNew}
                </button>
                <button
                  type="button"
                  className="pin-dialog__match-back"
                  onClick={() => setDetectedMatch(null)}
                  disabled={saving}
                >
                  {t.backToEdit}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="pin-dialog__field">
                <label
                  className="pin-dialog__label"
                  htmlFor={`${id}-initiative-desc`}
                >
                  {t.ideaLabel}
                </label>
                <textarea
                  id={`${id}-initiative-desc`}
                  className="pin-dialog__textarea"
                  name="description"
                  rows={5}
                  required
                  disabled={saving || checkingSimilarity}
                  placeholder={t.ideaPlaceholder}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </div>

              <footer className="pin-dialog__actions">
                <button
                  type="button"
                  className="pin-dialog__button"
                  onClick={() => dialogRef.current?.close()}
                  disabled={saving || checkingSimilarity}
                >
                  {t.cancel}
                </button>
                <button
                  type="submit"
                  className="pin-dialog__button pin-dialog__button--primary"
                  disabled={!canAdd || saving || checkingSimilarity}
                >
                  {checkingSimilarity
                    ? t.checking
                    : saving
                      ? t.saving
                      : t.sendInitiative}
                </button>
              </footer>
            </>
          )}
        </form>
      )}
    </dialog>
  );
}
