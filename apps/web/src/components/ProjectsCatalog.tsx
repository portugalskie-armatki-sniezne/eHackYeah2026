import { useEffect, useState } from "react";
import {
  projectsApi,
  type ProjectCategory,
  type ProjectSummary,
} from "../api/projects";
import "./ProjectsCatalog.css";

export default function ProjectsCatalog() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [categories, setCategories] = useState<ProjectCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [cats, projs] = await Promise.all([
          projectsApi.categories(),
          projectsApi.list({
            category: selectedCategory ?? undefined,
            q: searchQuery.trim() || undefined,
            limit: 100,
          }),
        ]);
        if (!ignore) {
          setCategories(cats);
          setProjects(projs.items);
        }
      } catch (err) {
        if (!ignore) {
          setError(
            err instanceof Error
              ? err.message
              : "Nie udało się załadować bazy innowacji.",
          );
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    const timer = setTimeout(() => {
      void loadData();
    }, 200);

    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [selectedCategory, searchQuery]);

  const totalCount = categories.reduce((sum, c) => sum + c.count, 0);

  return (
    <section className="catalog" aria-labelledby="catalog-title">
      <div className="catalog__frame">
        <div className="catalog__sheet">
          <header className="catalog__header">
            <div className="catalog__titles">
              <h1 id="catalog-title" className="catalog__title">
                Baza Innowacji Społecznych
              </h1>
              <p className="catalog__lede">
                Przeglądaj sprawdzone modele i innowacje z bazy ROPS Kraków.
                Zainspiruj się i zaproponuj ich realizację w swojej okolicy!
              </p>
            </div>
            <a className="catalog__back-button" href="#map">
              Wróć do mapy
            </a>
          </header>

          <div className="catalog__controls">
            <div className="catalog__search-bar">
              <input
                type="search"
                className="catalog__search-input"
                placeholder="Szukaj innowacji (np. seniorzy, tablica, integracja)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="catalog__categories" role="tablist">
              <button
                type="button"
                className={`catalog__cat-pill ${selectedCategory === null ? "catalog__cat-pill--active" : ""}`}
                onClick={() => setSelectedCategory(null)}
              >
                Wszystkie ({totalCount || projects.length})
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.category}
                  type="button"
                  className={`catalog__cat-pill ${selectedCategory === cat.category ? "catalog__cat-pill--active" : ""}`}
                  onClick={() =>
                    setSelectedCategory(
                      selectedCategory === cat.category ? null : cat.category,
                    )
                  }
                >
                  {cat.category} ({cat.count})
                </button>
              ))}
            </div>
          </div>

          {error && (
            <p className="catalog__error" role="alert">
              {error}
            </p>
          )}

          {loading ? (
            <div className="catalog__loading">
              Ładowanie innowacji społecznych...
            </div>
          ) : projects.length === 0 ? (
            <div className="catalog__empty">
              Nie znaleziono innowacji dla wybranych kryteriów.
            </div>
          ) : (
            <div className="catalog__grid">
              {projects.map((project) => {
                const isExpanded = expandedSlug === project.slug;
                return (
                  <article key={project.slug} className="catalog__card">
                    <div className="catalog__card-badge">
                      {project.category}
                    </div>
                    <h2 className="catalog__card-title">{project.title}</h2>

                    <p className="catalog__card-summary">
                      {project.description || project.summary}
                    </p>

                    {isExpanded && (
                      <div className="catalog__card-details">
                        {project.problem && (
                          <div className="catalog__card-section">
                            <strong>Problem:</strong>
                            <p>{project.problem}</p>
                          </div>
                        )}
                        {project.target_group && (
                          <div className="catalog__card-section">
                            <strong>Grupa docelowa:</strong>
                            <p>{project.target_group}</p>
                          </div>
                        )}
                        {project.beneficiaries && (
                          <div className="catalog__card-section">
                            <strong>Dla kogo:</strong>
                            <p>{project.beneficiaries}</p>
                          </div>
                        )}
                        {project.authors && (
                          <div className="catalog__card-section">
                            <strong>Autorzy:</strong>
                            <p>{project.authors}</p>
                          </div>
                        )}
                      </div>
                    )}

                    <footer className="catalog__card-footer">
                      <button
                        type="button"
                        className="catalog__card-btn-more"
                        onClick={() =>
                          setExpandedSlug(isExpanded ? null : project.slug)
                        }
                      >
                        {isExpanded ? "Zwiń opis" : "Szczegóły innowacji"}
                      </button>
                      <a
                        className="catalog__card-btn-action"
                        href="#map"
                        title="Przejdź na mapę i wskaż lokalizację"
                      >
                        Zaproponuj na mapie
                      </a>
                    </footer>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
