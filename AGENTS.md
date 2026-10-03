# AGENTS.md

## Project overview

- eHackYeah2026 is an application for reporting civic issues, proposing citizen initiatives, and tracking their progress.
- The planned stack is React Native with TypeScript for the frontend, Python with FastAPI for the backend, PostgreSQL, and Docker Compose.
- The repository currently has a React/Vite web scaffold in `apps/web` and an empty API workspace in `apps/api`.
- Docker Compose at the repository root starts PostGIS, applies migrations, and imports institution contacts with local defaults.
- Development should work on macOS, Windows, and Linux. Keep tooling and shared editor configuration portable.

## Working rules

- Always use classic dashes (`-`) rather than em dashes in code, comments, documentation, commit messages, and responses.
- Follow the repository's existing code structure, formatting, commenting, and documentation style. Read nearby files before editing and use established tooling when available.
- Never delete comments written by the user. If a comment conflicts with a requested change, point out the conflict and ask the user how to resolve it. The only exception is a TODO comment addressed by your changes, which may be removed when replaced with the corresponding implementation.
- Add code comments only when needed. Start them with lowercase letters and keep them simple, straightforward, and idiomatic, without excessive formatting.
- Make only changes needed to complete the requested task. Report unrelated errors or improvement opportunities instead of fixing them without being asked.
- Inspect the working tree before editing and preserve unrelated or pre-existing changes.
- Challenge unclear requirements or assumptions. Ask the user for clarification before implementing an ambiguous decision rather than inventing behavior, architecture, or scope. Continue independent work that does not depend on the answer.
- Validate that changes are correct and do not break related behavior. Review the final diff, run relevant available checks, and report their results and any checks that could not be run.
- Use `.gitkeep` to include otherwise empty directories in Git. Remove a directory's `.gitkeep` once it contains other tracked files.

## Architecture and repository layout

- `apps/web/` and `apps/api/` are frontend and backend workspaces.
- `db/migrations/` contains dbmate SQL migrations, with `-- migrate:up` and `-- migrate:down` sections.
- `db/seeds/` contains development and reference data, including the institution contacts workbook.
- `docker-compose.yaml` at the repository root defines the PostGIS database, dbmate migrations, and the seed importer. Run `docker compose up`; optional root `.env` values override local defaults.
- `tooling/seed/` contains the XLS importer with its `Dockerfile` and `requirements.txt`.
- `tooling/scripts/dev.ts` coordinates root development commands.
- `tests/e2e/` is reserved for cross-application scenarios, and `tests/fixtures/` for shared behavioral examples.
- `.agents/skills/` is reserved for repository-local agent skills.
- `.github/workflows/` is reserved for CI workflows.
- `.env` holds optional local environment overrides and is ignored by Git. `.env.example` documents the available values.
- `README.md` is the top-level project documentation.
- `TESTING.md` documents database setup and validation.

## Development command contract

- Use Bun 1.4+ and keep root commands limited to `bun install` and `bun run setup|all|web|api` unless requested otherwise.
- Workspaces provide `scripts.dev` and optional `scripts.setup`; API setup installs Python dependencies from its Python manifest. Keep setup repeatable and preserve `.env`.
- Scripts run in their application directory with root `.env` values. Keep servers in the foreground and reloads scoped to each application.
- The runner skips unimplemented applications and starts the database, migrations, and seed import before API startup.

## Validation

- Run `git diff --check` after changes and inspect changed and newly created files for unintended edits.
- For documentation changes, check grammar, Markdown structure, and affected links or table-of-contents anchors.
- For ignore-rule changes, check representative ignored and tracked paths with `git check-ignore`.
- For code or Docker changes, run the relevant configured formatting, build, test, and configuration checks, including checks for affected callers or services. Add or update regression tests when behavior changes warrant them.
- Validate Compose changes with `docker compose config --quiet`. Avoid printing resolved configuration because it can contain credentials.
- Run `bun test tooling/scripts/dev.test.ts` for runner changes and `python3 tests/check_database.py` for database changes. Report any unavailable checks.

## Secrets and local files

- Never commit real credentials, tokens, private keys, or populated secret files. Use placeholders in tracked examples and documentation.
- Keep secrets out of logs, command output, and shared VS Code configuration. `.gitignore` is not a substitute for reviewing files before staging.
- Store local secret values in `.env`. Keep `.env.example` tracked with the required variable names and placeholder values only, never real secrets.
