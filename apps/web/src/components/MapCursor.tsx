import { useEffect, useRef, useState, type RefObject } from "react";
import BrandMark from "./BrandMark";
import "./MapCursor.css";

type MapCursorProps = {
  targetRef: RefObject<HTMLElement | null>;
};

// Only mouse-like pointers have a cursor worth replacing; touch keeps MapLibre's own.
const FINE_POINTER = "(pointer: fine) and (hover: hover)";

const VISIBLE = "map-cursor--visible";
const PRESSED = "map-cursor--pressed";

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}

// Replaces the system cursor over the map with the brand mark: a drafting
// crosshair at the hotspot and the skyline tile as a badge that presses down onto
// its amber block while the map is being dragged, mirroring the toolbar buttons.
// Position is written straight to the DOM so pointer moves never re-render React.
export default function MapCursor({ targetRef }: MapCursorProps) {
  const finePointer = useMediaQuery(FINE_POINTER);
  const cursorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = targetRef.current;
    const cursor = cursorRef.current;
    if (!finePointer || !target || !cursor) {
      return;
    }

    const hide = () => cursor.classList.remove(VISIBLE, PRESSED);

    const move = (event: PointerEvent) => {
      if (event.pointerType === "touch") {
        hide();
        return;
      }
      cursor.style.transform = `translate3d(${event.clientX}px, ${event.clientY}px, 0)`;
      cursor.classList.add(VISIBLE);
    };

    const press = (event: PointerEvent) => {
      if (event.pointerType !== "touch" && event.button === 0) {
        cursor.classList.add(PRESSED);
      }
    };

    const release = () => cursor.classList.remove(PRESSED);

    target.addEventListener("pointermove", move);
    target.addEventListener("pointerdown", press);
    target.addEventListener("pointerleave", hide);
    // A drag can end anywhere, so the release is watched on the window.
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
    window.addEventListener("blur", hide);

    return () => {
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerdown", press);
      target.removeEventListener("pointerleave", hide);
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
      window.removeEventListener("blur", hide);
    };
  }, [finePointer, targetRef]);

  if (!finePointer) {
    return null;
  }

  return (
    <div ref={cursorRef} className="map-cursor" aria-hidden="true">
      <svg className="map-cursor__reticle" viewBox="-10 -10 20 20">
        <path
          className="map-cursor__reticle-halo"
          d="M-9 0 H-3 M3 0 H9 M0 -9 V-3 M0 3 V9"
        />
        <path
          className="map-cursor__reticle-line"
          d="M-9 0 H-3 M3 0 H9 M0 -9 V-3 M0 3 V9"
        />
        <rect
          className="map-cursor__reticle-dot"
          x="-1"
          y="-1"
          width="2"
          height="2"
        />
      </svg>
    </div>
  );
}
