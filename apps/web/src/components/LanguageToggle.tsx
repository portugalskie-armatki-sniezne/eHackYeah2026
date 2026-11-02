import { setLocale, useLocale, useMessages } from "../i18n/locale";
import { locales } from "../i18n/messages";
import "./LanguageToggle.css";

/**
 * A segmented tile with the current interface language filled in. The whole
 * tile is one button: a press anywhere on it moves to the next language. It
 * only switches the application's own text; what comes from the database
 * stays in the language it was written in.
 */
type LanguageToggleProps = {
  /** Id of a visible label; without it the button names itself. */
  labelledBy?: string;
};

export default function LanguageToggle({ labelledBy }: LanguageToggleProps) {
  const locale = useLocale();
  const t = useMessages();
  const next = locales[(locales.indexOf(locale) + 1) % locales.length];

  return (
    <button
      type="button"
      className="lang-toggle"
      aria-labelledby={labelledBy}
      onClick={() => setLocale(next)}
    >
      <span className="visually-hidden">
        {labelledBy ? `${t.language.names[locale]}. ` : ""}
        {t.language.switchTo(t.language.names[next])}
      </span>
      {locales.map((option) => (
        <span
          key={option}
          lang={option}
          className="lang-toggle__option"
          data-current={option === locale ? "true" : undefined}
          aria-hidden="true"
        >
          {option.toUpperCase()}
        </span>
      ))}
    </button>
  );
}
