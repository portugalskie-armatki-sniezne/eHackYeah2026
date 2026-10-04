import LanguageToggle from "./LanguageToggle";
import useHashRoute from "./useHashRoute";
import "./LanguageCorner.css";

/**
 * The language switch pinned to the bottom-right corner of every page, so it
 * is one tap away whether or not someone is signed in. On the map it shares
 * the bottom edge with the toolbar and steps above it where a phone leaves no
 * room beside it.
 */
export default function LanguageCorner() {
  const onMap = useHashRoute() === "map";
  return (
    <div className={onMap ? "lang-corner lang-corner--on-map" : "lang-corner"}>
      <LanguageToggle />
    </div>
  );
}
