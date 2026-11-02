import { useEffect, useId, useState } from "react";
import {
  projectsApi,
  type ProjectCategory,
  type ProjectSummary,
} from "../api/projects";
import { useMessages } from "../i18n/locale";
import type { Messages } from "../i18n/messages";
import "./ProjectsCatalog.css";

type CatalogMessages = Messages["catalog"];

// the library holds a little over a hundred innovations, so one page is the whole list
const PAGE_LIMIT = 200;

/**
 * The ROPS social innovation library as a list anyone can browse: a search
 * box, the categories as pills, and one card per innovation with its sections
 * folded under it. It takes the map's place on the sheet, like the reports page.
 */
export default function ProjectsCatalog() {
  const t = useMessages().catalog;
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [categories, setCategories] = useState<ProjectCategory[]>([]);
  const [category, setCategory] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  // the list comes filtered from the api, a moment after the last keystroke
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const timer = setTimeout(() => {
      Promise.all([
        projectsApi.categories(signal),
        projectsApi.list(
          {
            category: category ?? undefined,
            q: query.trim() || undefined,
            limit: PAGE_LIMIT,
          },
          signal,
        ),
      ]).then(
        ([list, page]) => {
          if (signal.aborted) return;
          setCategories(list);
          setProjects(page.items);
          setError(null);
        },
        (error) => {
          if (signal.aborted) return;
          setError(error instanceof Error ? error.message : t.loadFailed);
        },
      );
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
    // the strings only matter for the fallback message
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, query]);

  const total = categories.reduce((sum, item) => sum + item.count, 0);

  return (
    <section className="catalog" aria-labelledby="catalog-title">
      <div className="catalog__frame">
        <div className="catalog__sheet">
          <header className="catalog__header">
            <h1 id="catalog-title" className="catalog__title">
              {t.title}
            </h1>
            <p className="catalog__lede">{t.lede}</p>
            <a className="catalog__button" href="#map">
              {t.backToMap}
            </a>
          </header>

          <div className="catalog__controls">
            <label className="catalog__search">
              <span className="visually-hidden">{t.search}</span>
              <input
                type="search"
                className="catalog__input"
                placeholder={t.searchPlaceholder}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div
              className="catalog__pills"
              role="group"
              aria-label={t.categoryFilter}
            >
              <button
                type="button"
                className="catalog__pill"
                aria-pressed={category === null}
                onClick={() => setCategory(null)}
              >
                {t.all(total)}
              </button>
              {categories.map((item) => (
                <button
                  key={item.category}
                  type="button"
                  className="catalog__pill"
                  title={`${item.category} (${item.count})`}
                  aria-pressed={category === item.category}
                  onClick={() =>
                    setCategory(
                      category === item.category ? null : item.category,
                    )
                  }
                >
                  {item.category} ({item.count})
                </button>
              ))}
            </div>
            {projects && (
              <p className="catalog__count">
                {t.shown(projects.length, total)}
              </p>
            )}
          </div>

          {error && (
            <p className="catalog__error" role="alert">
              {error}
            </p>
          )}

          {projects === null && !error ? (
            <p className="catalog__state">{t.loading}</p>
          ) : projects && projects.length === 0 ? (
            <p className="catalog__state">{t.empty}</p>
          ) : (
            projects && (
              <ul className="catalog__list">
                {projects.map((project) => (
                  <li key={project.slug}>
                    <ProjectCard project={project} t={t} />
                  </li>
                ))}
              </ul>
            )
          )}
        </div>
      </div>
    </section>
  );
}

type ProjectCardProps = {
  project: ProjectSummary;
  t: CatalogMessages;
};

/**
 * One innovation: its category, title and lead, the way to its page and to
 * the map, and the sections of its page folded under it.
 */
function ProjectCard({ project, t }: ProjectCardProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const sections = (
    [
      [t.description, project.description],
      [t.problem, project.problem],
      [t.targetGroup, project.target_group],
      [t.beneficiaries, project.beneficiaries],
      [t.effectiveness, project.effectiveness],
      [t.authors, project.authors],
    ] as const
  ).filter((entry): entry is [string, string] => Boolean(entry[1]));

  return (
    <article className="catalog__card" aria-labelledby={`${id}-title`}>
      <header className="catalog__card-head">
        <div className="catalog__card-meta">
          <span className="catalog__badge">{project.category}</span>
        </div>
        <h2 id={`${id}-title`} className="catalog__card-title">
          {project.title}
        </h2>
        <p className="catalog__card-text">{project.summary}</p>
      </header>

      <div className="catalog__actions">
        <a
          className="catalog__button"
          href={project.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t.source}
        </a>
        <a
          className="catalog__button catalog__button--primary"
          href="#map"
          title={t.proposeTitle}
        >
          {t.proposeOnMap}
        </a>
      </div>

      {sections.length > 0 && (
        <section className="catalog__more" aria-labelledby={`${id}-fold`}>
          <button
            type="button"
            id={`${id}-fold`}
            className="catalog__fold"
            aria-expanded={open}
            aria-controls={`${id}-details`}
            onClick={() => setOpen((current) => !current)}
          >
            <span className="catalog__caret" aria-hidden="true" />
            {open ? t.collapse : t.details}
          </button>
          {open && (
            <dl id={`${id}-details`} className="catalog__details">
              {sections.map(([label, text]) => (
                <div key={label} className="catalog__section">
                  <dt>{label}</dt>
                  <dd>{text}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      )}
    </article>
  );
}
