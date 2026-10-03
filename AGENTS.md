# AGENTS.md

## Project overview

- eHackYeah2026 is an application for reporting civic issues, proposing citizen initiatives, and tracking their progress.
- The planned stack is React Native with TypeScript for the frontend, Python with FastAPI for the backend, PostgreSQL, and Docker Compose.
- The repository has a React/Vite frontend in `apps/web`, a FastAPI backend in `apps/api`, and a separate SMTP relay in `apps/notify`.
- Docker Compose at the repository root starts PostGIS, applies migrations, and imports institution contacts with local defaults.
- Development should work on macOS, Windows, and Linux. Keep tooling and shared editor configuration portable.

## Working rules

- Always use classic dashes (`-`) rather than em dashes in code, comments, documentation, commit messages, and responses.
- Never use emoji in pull request titles, descriptions, or comments.
- Follow the repository's existing code structure, formatting, commenting, and documentation style. Read nearby files before editing and use established tooling when available.
- Never delete comments written by the user. If a comment conflicts with a requested change, point out the conflict and ask the user how to resolve it. The only exception is a TODO comment addressed by your changes, which may be removed when replaced with the corresponding implementation.
- Add code comments only when needed. Start them with lowercase letters and keep them simple, straightforward, and idiomatic, without excessive formatting.
- Make only changes needed to complete the requested task. Report unrelated errors or improvement opportunities instead of fixing them without being asked.
- Inspect the working tree before editing and preserve unrelated or pre-existing changes.
- Challenge unclear requirements or assumptions. Ask the user for clarification before implementing an ambiguous decision rather than inventing behavior, architecture, or scope. Continue independent work that does not depend on the answer.
- Validate that changes are correct and do not break related behavior. Review the final diff, run relevant available checks, and report their results and any checks that could not be run.
- Use `.gitkeep` to include otherwise empty directories in Git. Remove a directory's `.gitkeep` once it contains other tracked files.

## README maintenance

- Maintain `README.md` and `README_pl.md` together in the same change. Keep their sections, facts, and commands aligned; write idiomatic English and Polish rather than literal translations.
- Preserve the project name, language links, teasers, section order, and existing visual style. Use short, plain sentences, numbered instructions, and concise bullets.
- Avoid boilerplate, repeated setup instructions, and implementation details that do not help the reader. Keep setup and startup instructions in the deployment section.
- Keep teaser files in `docs/` and include them in both repository layouts. Check both READMEs for broken links, missing images, empty link targets, and duplicate sections after editing.

## Architecture and repository layout

- `apps/web/`, `apps/api/`, and `apps/notify/` are frontend, backend, and mail relay workspaces. `apps/api/docs/` and `apps/notify/docs/` document their implemented behavior.
- `db/migrations/` contains dbmate SQL migrations, with `-- migrate:up` and `-- migrate:down` sections.
- `db/seeds/` contains development and reference data, including the institution contacts workbook.
- `docker-compose.yaml` at the repository root defines the PostGIS database, dbmate migrations, and the seed importer. Run `docker compose up`; optional root `.env` values override local defaults.
- `docker-compose.app.yaml` defines the `api`, `web`, and `notify` containers, which run published images selected by `API_IMAGE_TAG`, `WEB_IMAGE_TAG`, and `NOTIFY_IMAGE_TAG`. The `api` container reaches the database through the external network named by `DB_NETWORK` and stores report photos on the `api_uploads` volume.
- `notify` shares the application network with `api` and exposes only an internal HTTP port selected by `NOTIFY_PORT`. It sends mail through Gmail SMTP using `SMTP_USER` and `SMTP_PASSWORD`. `SMTP_MOCK=true` redirects every mail to `SMTP_MOCK_DESTINATION`; an invalid test destination blocks sending.
- `notify/templates/` contains Markdown templates for `issue` and `improvement`, rendered to HTML with a text alternative. `POST /send` inserts `description` and the reporter's `first_name` and `last_name`; `anonymous=true` omits their name. Optional `location` generates a Google Maps link, and `photos` uses API `storage_key` values from the shared `api_uploads` volume mounted read-only.
- `tooling/seed/` contains the XLS importer with its `Dockerfile`, `pyproject.toml`, and `uv.lock`, and the mock demo data importer with its photos.
- `docker compose run --rm mock-seeder` replaces mock demo data in Kraków; its `mock` profile keeps it out of `docker compose up`.
- `Taskfile.yml` at the repository root defines root development commands. `mise.toml` pins Bun, Task, and uv, and `setup-dev-env.sh` installs mise, the pinned tools, and dependencies.
- `tests/e2e/` is reserved for cross-application scenarios, and `tests/fixtures/` for shared behavioral examples.
- `.agents/skills/` is reserved for repository-local agent skills.
- `.github/workflows/` contains CI workflows. `deploy.yml` builds the web, API, and notify images and deploys them: the changed services to the dev environment when changes reach `main`, or the chosen service, or all of them, to the environment chosen in a manual run. Every deployment copies `docker-compose.app.yaml` to the deployment directory as `docker-compose.yml`. Before restarting `api`, it applies `db/migrations` to the database of the target environment. `release.yml` is started manually: it calls `deploy.yml` to deploy all three services to prod, then publishes a GitHub release versioned by date. `lint.yml` runs the web, API, and notify linters on pull requests and pushes to `main`. `seed.yml` is started manually: it imports `db/seeds` into the database of the chosen environment with the importer from `tooling/seed`.
- `.env` holds optional local environment overrides and is ignored by Git. `.env.example` documents the available values.
- `README.md` and `README_pl.md` are the English and Polish project documentation. `docs/` contains their teaser images.
- `TESTING.md` documents database setup and validation.

## Development command contract

- Use the Bun, Task, and uv versions pinned in `mise.toml` and keep root commands limited to `./setup-dev-env.sh` and `task setup|web|db|api|fe:lint|fe:lint:fix|be:lint|be:lint:fix` unless requested otherwise.
- The web workspace provides `scripts.dev`; API setup installs Python dependencies from its Python manifest with uv. Keep setup repeatable and preserve `.env`.
- Tasks run applications in their directory with root `.env` values. Keep servers in the foreground and reloads scoped to each application.
- Both `db` and `api` start the database, migrations, and seed import.

## Validation

- Run `git diff --check` after changes and inspect changed and newly created files for unintended edits.
- For documentation changes, check grammar, Markdown structure, and affected links or table-of-contents anchors.
- For ignore-rule changes, check representative ignored and tracked paths with `git check-ignore`.
- For code or Docker changes, run the relevant configured formatting, build, test, and configuration checks, including checks for affected callers or services. Add or update regression tests when behavior changes warrant them.
- For web changes, run `task fe:lint`. For API changes, run `task be:lint`.
- For notify changes, run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` from `apps/notify`. Its tests replace SMTP and do not send mail.
- Validate Compose changes with `docker compose config --quiet`. Avoid printing resolved configuration because it can contain credentials.
- Run `task --list-all` and the affected tasks for Taskfile changes and `python3 tests/check_database.py` for database changes. Report any unavailable checks.

## Secrets and local files

- Never commit real credentials, tokens, private keys, or populated secret files. Use placeholders in tracked examples and documentation.
- Keep secrets out of logs, command output, and shared VS Code configuration. `.gitignore` is not a substitute for reviewing files before staging.
- Store local secret values in `.env`. Keep `.env.example` tracked with the required variable names and placeholder values only, never real secrets.
