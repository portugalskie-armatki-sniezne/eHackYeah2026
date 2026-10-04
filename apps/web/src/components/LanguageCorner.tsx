import LanguageToggle from "./LanguageToggle";
import "./LanguageCorner.css";

/**
 * The language switch pinned to the bottom-right corner of every page, so it
 * is one tap away whether or not someone is signed in. A phone has no room
 * for it beside the full-width map toolbar, so there it is hidden.
 */
export default function LanguageCorner() {
  return (
    <div className="lang-corner">
      <LanguageToggle />
    </div>
  );
}
