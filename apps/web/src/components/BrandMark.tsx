import "./BrandMark.css";

type BrandMarkProps = {
  className?: string;
};

// The skyline mark: a stepped row of paper buildings outlined in ink, lifted off
// an amber block the same way the nav, toolbar and map tiles sit on theirs.
// Shared by the navbar brand and the map cursor so the two read as one object.
export default function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg
      className={className ? `brand-mark ${className}` : "brand-mark"}
      viewBox="0 0 48 30"
      aria-hidden="true"
      focusable="false"
    >
      <rect className="brand-mark__block" x="7" y="7" width="38" height="20" />
      <path
        className="brand-mark__line"
        d="M2 23 V13 H9 V8 H15 V3 H22 V10 H28 V6 H34 V15 H40 V23 Z"
      />
    </svg>
  );
}
