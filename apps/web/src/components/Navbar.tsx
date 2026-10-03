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

export default function Navbar() {
  return (
    <header className="navbar">
      <a className="navbar__skip" href="#main">
        Skip to map
      </a>
      <div className="navbar__pill">
        <a className="navbar__brand" href="#map">
          eHackYeah<span className="navbar__brand-accent">2026</span>
        </a>
        <nav aria-label="Main">
          <ul className="navbar__list">
            {items.map((item, index) => (
              <li key={item.href}>
                <a
                  className="navbar__link"
                  href={item.href}
                  aria-current={index === 0 ? "page" : undefined}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
