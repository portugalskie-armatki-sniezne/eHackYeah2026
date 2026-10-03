# AGENTS.md

## Project overview

- eHackYeah2026 is a web application for reporting civic issues, proposing citizen initiatives, and tracking their progress.
- The repository is currently a scaffold. The web and API directories are empty placeholders; application frameworks, dependencies, and commands are not configured yet. Do not treat the previous React Native, Vite, or FastAPI plans as an implemented stack.
- PostgreSQL and dbmate are configured through Docker Compose in `infra/compose.yaml`.
- `package.json`, `bun.lock`, and `TESTING.md` are currently empty placeholders. Do not assume package scripts, a working Bun workspace, or a test runner exist.
- Development should work on macOS, Windows, and Linux. Keep tooling and shared editor configuration portable.

## Working rules

- Always use classic dashes (`-`) rather than em dashes in code, comments, documentation, commit messages, and responses.
- Follow the repository's existing code structure, formatting, commenting, and documentation style. Read nearby files before editing and use established tooling when available.
- Never delete comments written by the user. If a comment conflicts with a requested change, point out the conflict and ask the user how to resolve it. The only exception is a TODO comment addressed by your changes, which may be removed when replaced with the corresponding implementation.
- Add code comments only when needed. Keep them simple, straightforward, and idiomatic, without excessive formatting.
- Make only changes needed to complete the requested task. Report unrelated errors or improvement opportunities instead of fixing them without being asked.
- Inspect the working tree before editing and preserve unrelated or pre-existing changes.
- Challenge unclear requirements or assumptions. Ask the user for clarification before implementing an ambiguous decision rather than inventing behavior, architecture, or scope. Continue independent work that does not depend on the answer.
- Validate that changes are correct and do not break related behavior. Review the final diff, run relevant available checks, and report their results and any checks that could not be run.
- Use `.gitkeep` to include otherwise empty directories in Git. Remove a directory's `.gitkeep` once it contains other tracked files.

## Architecture and repository layout

- `apps/web/` is the web application directory, currently containing only `.gitkeep`.
- `apps/api/` is the backend application directory, currently containing only `.gitkeep`.
- `db/migrations/` contains dbmate SQL migrations. Each migration must include both `-- migrate:up` and `-- migrate:down` sections. The existing migration creates the example `example_items` table.
- `db/seeds/` is reserved for development and reference data.
- `infra/compose.yaml` defines PostgreSQL and a one-shot dbmate migration service. It mounts `db/` into the migration container and stores PostgreSQL data in the `postgres_data` named volume. Schema dumping is disabled with `DBMATE_NO_DUMP_SCHEMA`; there is currently no generated `db/schema.sql`.
- `tooling/scripts/` is reserved for development and maintenance scripts.
- `tests/e2e/` is reserved for cross-application scenarios, and `tests/fixtures/` for shared behavioral examples. Keep application-specific tests near their application code when a test setup is introduced.
- `.agents/skills/` is reserved for repository-local agent skills.
- `.github/workflows/` is reserved for CI workflows; none are configured yet.
- `.env` holds local environment values and is ignored by Git. `.env.example` documents the variables required by Docker Compose.
- `README.md` is the top-level project documentation.
- `TESTING.md` is the place to document test setup and commands once they exist.

## Local infrastructure

- Create a root `.env` from `.env.example` if it does not exist.
- From the repository root, run `docker compose --env-file .env -f infra/compose.yaml up -d` to start PostgreSQL and apply migrations.

## Validation

- Run `git diff --check` after changes and inspect changed and newly created files for unintended edits.
- For documentation changes, check grammar, Markdown structure, and affected links or table-of-contents anchors.
- For ignore-rule changes, check representative ignored and tracked paths with `git check-ignore`.
- For code or Docker changes, run the relevant configured formatting, build, test, and configuration checks, including checks for affected callers or services. Add or update regression tests when behavior changes warrant them.
- Validate Compose changes with `docker compose --env-file .env -f infra/compose.yaml config --quiet`. For configuration-only checks without a local `.env`, use `.env.example` instead. Avoid printing resolved configuration because it can contain credentials.
- Application lint, build, and test commands are not available yet. Once configured, document the actual commands in `README.md` and `TESTING.md`; until then, report the validation gap instead of inventing commands.

## Secrets and local files

- Never commit real credentials, tokens, private keys, or populated secret files. Use placeholders in tracked examples and documentation.
- Keep secrets out of logs, command output, and shared VS Code configuration. `.gitignore` is not a substitute for reviewing files before staging.
- Store local secret values in `.env`. Keep `.env.example` tracked with the required variable names and placeholder values only, never real secrets.
