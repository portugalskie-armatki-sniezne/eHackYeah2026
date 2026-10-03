import "./About.css";

type Pillar = {
  title: string;
  text: string;
};

type Step = {
  title: string;
  text: string;
};

const pillars: Pillar[] = [
  {
    title: "Report local issues",
    text: "A broken lamp, a pothole, an overflowing bin. Pin it on the map, add a photo, we will contact apropriete services",
  },
  {
    title: "Propose initiatives",
    text: "A bench, a crossing, a bike rack. Put the idea where it belongs and let neighbours back it.",
  },
  {
    title: "Track their progress",
    text: "Every case carries a shared status and the institution's response, so nobody has to ask twice.",
  },
];

const steps: Step[] = [
  {
    title: "Drop a pin",
    text: "Click the map where something is wrong, or take a photo from where you stand. The pin keeps the GPS position and the picture.",
  },
  {
    title: "Describe it",
    text: "A sentence is enough. The report is saved right away, before anything else happens to it.",
  },
  {
    title: "Let the machine find the office",
    text: "Deterministic classifiers and generative models read the text and the photo, decide what kind of service the problem needs, and pick the authority responsible for it from a database built from publicly available information about institutions.",
  },
  {
    title: "One issue, one case",
    text: "Reports about the same thing in the same place are merged into one master report, so one broken lamp is one case and not twenty.",
  },
  {
    title: "Follow it",
    text: "Comment, like, and watch the status change until the case is finished.",
  },
];

/**
 * The about page: what the application is for and how a report travels from
 * a pin on the map to the desk that can fix it. It takes the map's place on
 * the sheet and keeps the navbar above it.
 */
export default function About() {
  return (
    <section className="about" aria-labelledby="about-title">
      <div className="about__frame">
        <div className="about__sheet">
          <header className="about__header">
            <h1 id="about-title" className="about__title">
              pomożeMy
            </h1>
            <p className="about__lede">
              A unified platform for reporting local issues, proposing citizen
              initiatives, and tracking their progress. Changing your city
              without excessive complications.
            </p>
            <a className="about__button" href="#map">
              Go back to map
            </a>
          </header>

          <ul className="about__pillars">
            {pillars.map((pillar) => (
              <li key={pillar.title} className="about__tile">
                <h2 className="about__tile-title">{pillar.title}</h2>
                <p className="about__tile-text">{pillar.text}</p>
              </li>
            ))}
          </ul>

          <section className="about__section" aria-labelledby="about-how">
            <h2 id="about-how" className="about__heading">
              How a report travels
            </h2>
            <ol className="about__steps">
              {steps.map((step, index) => (
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
              Why it exists
            </h2>
            <p className="about__text">
              Telling the right public institution about a problem should not
              require knowing which institution that is. Finding the office, the
              form, and the address is work that keeps people from reporting at
              all, and the same problem gets reported many times by whoever
              does. pomożeMy keeps the map, the photos, and the conversation in
              one place, works out who is responsible, and lets everyone see
              what happened next.
            </p>
          </section>
        </div>
      </div>
    </section>
  );
}
