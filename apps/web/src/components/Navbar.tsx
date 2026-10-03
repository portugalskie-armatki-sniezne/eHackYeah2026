import { useEffect, useId, useRef, useState } from "react";
import type { SessionState } from "../api/session";
import BrandMark from "./BrandMark";
import useHashRoute from "./useHashRoute";
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
  onProfile: () => void;
};

export default function Navbar({
  session,
  onSignIn,
  onSignOut,
  onProfile,
}: NavbarProps) {
  // only matters on narrow screens, where the list folds behind the hamburger
  const [open, setOpen] = useState(false);
  const menuId = useId();
  // the map is current for every hash that is not its own page
  const current = `#${useHashRoute()}`;

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
                  aria-current={item.href === current ? "page" : undefined}
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
              <AccountMenu
                name={session.user.first_name}
                onProfile={() => {
                  setOpen(false);
                  onProfile();
                }}
                onSignOut={() => {
                  setOpen(false);
                  onSignOut();
                }}
              />
            ) : (
              <button
                type="button"
                className="navbar__link navbar__button"
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
type AccountMenuProps = {
  name: string;
  onProfile: () => void;
  onSignOut: () => void;
};

/**
 * The user's name as a tile that unfolds the account actions. It closes on
 * Escape, on a click elsewhere, when focus leaves it, and after a choice.
 */
function AccountMenu({ name, onProfile, onSignOut }: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }
    const closeOnOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOnOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const choose = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <div
      ref={rootRef}
      className="navbar__account-menu"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
        }
      }}
    >
      <button
        ref={toggleRef}
        type="button"
        className="navbar__link navbar__button navbar__user"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="visually-hidden">Signed in as </span>
        <span className="navbar__user-name">{name}</span>
        <span className="navbar__caret" aria-hidden="true" />
      </button>
      <ul id={menuId} className="navbar__menu" hidden={!open}>
        <li>
          <button
            type="button"
            className="navbar__menu-item"
            onClick={() => choose(onProfile)}
          >
            My Profile
          </button>
        </li>
        <li>
          <button
            type="button"
            className="navbar__menu-item"
            onClick={() => choose(onSignOut)}
          >
            Logout
          </button>
        </li>
      </ul>
    </div>
  );
}
