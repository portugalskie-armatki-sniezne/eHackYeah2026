import { useEffect, useId, useState } from "react";
import type { SessionState } from "../api/useSession";
import BrandMark from "./BrandMark";
import "./Navbar.css";

type NavItem = {
  href: string;
  label: string;
};

const items: NavItem[] = [
  { href: "#map", label: "Map" },
  { href: "#reports", label: "Reports" },
  { href: "#initiatives", label: "Initiatives" },
  { href: "#about", label: "About" },
];

type NavbarProps = {
  session: SessionState;
  onSignIn: () => void;
  onSignOut: () => void;
};

export default function Navbar({ session, onSignIn, onSignOut }: NavbarProps) {
  // only matters on narrow screens, where the list folds behind the hamburger
  const [open, setOpen] = useState(false);
  const menuId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);

  return (
    <header className="navbar">
      <a className="navbar__skip" href="#main">
        Skip to map
      </a>
      <div
        className={open ? "navbar__frame navbar__frame--open" : "navbar__frame"}
      >
        <a className="navbar__brand" href="#map">
          <BrandMark className="navbar__mark" />
          <span className="navbar__wordmark">
            eHackYeah<span className="navbar__brand-accent">2026</span>
          </span>
        </a>
        <button
          type="button"
          className="navbar__toggle"
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => setOpen((current) => !current)}
        >
          <span className="navbar__burger" aria-hidden="true">
            <span className="navbar__burger-bar" />
            <span className="navbar__burger-bar" />
            <span className="navbar__burger-bar" />
          </span>
          <span className="visually-hidden">
            {open ? "Close menu" : "Open menu"}
          </span>
        </button>
        <nav id={menuId} className="navbar__nav" aria-label="Main">
          <ul className="navbar__list">
            {items.map((item, index) => (
              <li key={item.href} className="navbar__item">
                {index > 0 && (
                  <span className="navbar__divider" aria-hidden="true" />
                )}
                <a
                  className="navbar__link"
                  href={item.href}
                  aria-current={index === 0 ? "page" : undefined}
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        {session.status !== "checking" && (
          <div className="navbar__account">
            {session.status === "signed-in" ? (
              <>
                <span className="navbar__user">
                  <span className="visually-hidden">Signed in as </span>
                  {session.session.user.first_name}
                </span>
                <button
                  type="button"
                  className="navbar__link navbar__button"
                  onClick={() => {
                    setOpen(false);
                    onSignOut();
                  }}
                >
                  Sign out
                </button>
              </>
            ) : (
              <button
                type="button"
                className="navbar__link navbar__button navbar__button--primary"
                onClick={() => {
                  setOpen(false);
                  onSignIn();
                }}
              >
                Sign in
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
