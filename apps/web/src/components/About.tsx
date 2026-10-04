import { useMessages } from "../i18n/locale";
import "./About.css";

/**
 * The about page: what the application is for and how a report travels from
 * a pin on the map to the desk that can fix it. It takes the map's place on
 * the sheet and keeps the navbar above it. Its copy follows the language
 * toggle; the product name does not.
 */
export default function About() {
  const t = useMessages().about;

  return (
    <section className="about" aria-labelledby="about-title">
      <div className="about__frame">
        <div className="about__sheet">
          <header className="about__header">
            <h1 id="about-title" className="about__title">
              pomożeMy
            </h1>
            <p className="about__lede">{t.lede}</p>
            <a className="about__button" href="#map">
              {t.backToMap}
            </a>
          </header>

          <ul className="about__pillars">
            {t.pillars.map((pillar) => (
              <li key={pillar.title} className="about__tile">
                <h2 className="about__tile-title">{pillar.title}</h2>
                <p className="about__tile-text">{pillar.text}</p>
              </li>
            ))}
          </ul>

          <section className="about__section" aria-labelledby="about-how">
            <h2 id="about-how" className="about__heading">
              {t.howHeading}
            </h2>
            <ol className="about__steps">
              {t.steps.map((step, index) => (
                <li key={step.title} className="about__step">
                  <span className="about__step-number" aria-hidden="true">
                    {index + 1}
                  </span>
                  <div className="about__step-body">
                    <h3 className="about__step-title">{step.title}</h3>
                    <p className="about__step-text">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="about__section" aria-labelledby="about-why">
            <h2 id="about-why" className="about__heading">
              {t.whyHeading}
            </h2>
            <p className="about__text">{t.whyText}</p>
          </section>
        </div>
      </div>
    </section>
  );
}
