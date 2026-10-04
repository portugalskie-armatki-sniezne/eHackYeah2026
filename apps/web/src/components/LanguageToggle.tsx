import { setLocale, useLocale, useMessages } from "../i18n/locale";
import { locales } from "../i18n/messages";
import "./LanguageToggle.css";

/**
 * A segmented tile with one pressed button per interface language. It only
 * switches the application's own text; what comes from the database stays
 * in the language it was written in.
 */
type LanguageToggleProps = {
  /** Id of a visible label; without it the group names itself. */
  labelledBy?: string;
};

export default function LanguageToggle({ labelledBy }: LanguageToggleProps) {
  const locale = useLocale();
  const t = useMessages();

  return (
    <div
      className="lang-toggle"
      role="group"
      aria-label={labelledBy ? undefined : t.language.label}
      aria-labelledby={labelledBy}
    >
      {locales.map((option) => (
        <button
          key={option}
          type="button"
          lang={option}
          className="lang-toggle__option"
          aria-pressed={option === locale}
          onClick={() => setLocale(option)}
        >
          <span aria-hidden="true">{option.toUpperCase()}</span>
          <span className="visually-hidden">{t.language.names[option]}</span>
        </button>
      ))}
    </div>
  );
}
