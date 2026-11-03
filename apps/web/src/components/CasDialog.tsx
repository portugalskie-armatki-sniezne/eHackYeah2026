import { useEffect, useRef } from "react";
import type { KrakowCasCenter } from "../data/krakowCas";
import { krakowCasSource } from "../data/krakowCas";
import "./CasDialog.css";

type CasDialogProps = {
  cas: KrakowCasCenter;
  onClose: () => void;
  onStartInitiative?: (coordinates: [number, number], title: string) => void;
};

export default function CasDialog({
  cas,
  onClose,
  onStartInitiative,
}: CasDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) return;
    dialog.showModal();
  }, []);

  const handleInitiativeClick = () => {
    onClose();
    onStartInitiative?.(cas.coordinates, `Inicjatywa senioralna: ${cas.name}`);
  };

  return (
    <dialog
      ref={dialogRef}
      className="cas-dialog"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          onClose();
        }
      }}
    >
      <div className="cas-dialog__content">
        <div className="cas-dialog__header">
          <div className="cas-dialog__badges">
            <span className="cas-dialog__badge cas-dialog__badge--cas">
              Centrum Aktywności Seniora
            </span>
            <span className="cas-dialog__badge cas-dialog__badge--opendata">
              Otwarte Dane UMK
            </span>
          </div>
          <button
            type="button"
            className="cas-dialog__close"
            onClick={onClose}
            aria-label="Zamknij"
          >
            &times;
          </button>
        </div>

        <h2 className="cas-dialog__title">{cas.name}</h2>

        <div className="cas-dialog__details">
          <div className="cas-dialog__row">
            <span className="cas-dialog__label">Podmiot prowadzący (NGO)</span>
            <span className="cas-dialog__value">{cas.operator}</span>
          </div>

          <div className="cas-dialog__row">
            <span className="cas-dialog__label">Adres</span>
            <span className="cas-dialog__value">
              {cas.address}, {cas.postalCode} Kraków
            </span>
          </div>

          <div className="cas-dialog__row">
            <span className="cas-dialog__label">Dzielnica</span>
            <span className="cas-dialog__value">
              Dzielnica {cas.districtRoman} {cas.districtName}
            </span>
          </div>

          {cas.phone && (
            <div className="cas-dialog__row">
              <span className="cas-dialog__label">Kontakt telefoniczny</span>
              <a href={`tel:${cas.phone}`} className="cas-dialog__link">
                {cas.phone}
              </a>
            </div>
          )}

          {cas.notes && (
            <div className="cas-dialog__row">
              <span className="cas-dialog__label">Uwagi</span>
              <span className="cas-dialog__value">{cas.notes}</span>
            </div>
          )}
        </div>

        <div className="cas-dialog__actions">
          {onStartInitiative && (
            <button
              type="button"
              className="cas-dialog__button cas-dialog__button--primary"
              onClick={handleInitiativeClick}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
              Zgłoś inicjatywę w tej okolicy
            </button>
          )}

          <a
            href={krakowCasSource.portalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="cas-dialog__button cas-dialog__button--secondary"
          >
            Zobacz zbiór na Otwarte Dane Kraków ↗
          </a>
        </div>
      </div>
    </dialog>
  );
}
