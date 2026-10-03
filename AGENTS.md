# AGENTS.md

## Project overview

- eHackYeah2026 is a web application for reporting civic issues, proposing citizen initiatives, and tracking their progress.
- The repository is a scaffold with web and API workspaces. Application frameworks are not implemented yet.
- PostgreSQL and dbmate are configured through Docker Compose in `infra/compose.yaml`.
- `package.json` and `bun.lock` configure Bun workspaces and root commands. `TESTING.md` remains empty.
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

- `apps/web/` and `apps/api/` are web and backend workspaces; application code is not implemented yet.
- `db/migrations/` contains dbmate SQL with `-- migrate:up` and `-- migrate:down` sections.
- `db/seeds/` is reserved for development and reference data.
- `infra/compose.yaml` defines PostgreSQL on localhost and dbmate, with persistent database storage and schema dumps disabled.
- `tooling/scripts/dev.ts` coordinates root development commands.
- `tests/e2e/` is reserved for cross-application scenarios, and `tests/fixtures/` for shared behavioral examples. Keep application-specific tests near their application code when a test setup is introduced.
- `.agents/skills/` is reserved for repository-local agent skills.
- `.github/workflows/` is reserved for CI workflows; none are configured yet.
- `.env` holds local environment values and is ignored by Git. `.env.example` documents the variables required by Docker Compose.
- `README.md` is the top-level project documentation.
- `TESTING.md` is the place to document test setup and commands once they exist.

## Development command contract

- Use Bun 1.4+ and keep root commands limited to `bun install` and `bun run setup|all|web|api` unless requested otherwise.
- Workspaces provide `scripts.dev` and optional `scripts.setup`; API setup installs Python dependencies from its Python manifest. Keep setup repeatable and preserve `.env`.
- Scripts run in their application directory with root `.env` values. Keep servers in the foreground and reloads scoped to each application.
- The runner skips unimplemented applications and handles PostgreSQL and migrations before API startup.

## Validation

- Run `git diff --check` after changes and inspect changed and newly created files for unintended edits.
- For documentation changes, check grammar, Markdown structure, and affected links or table-of-contents anchors.
- For ignore-rule changes, check representative ignored and tracked paths with `git check-ignore`.
- For code or Docker changes, run the relevant configured formatting, build, test, and configuration checks, including checks for affected callers or services. Add or update regression tests when behavior changes warrant them.
- Validate Compose changes with `docker compose --env-file .env -f infra/compose.yaml config --quiet`. For configuration-only checks without a local `.env`, use `.env.example` instead. Avoid printing resolved configuration because it can contain credentials.
- Run `bun test tooling/scripts/dev.test.ts` for runner changes. Application checks are not configured yet; report that gap.

## Secrets and local files

- Never commit real credentials, tokens, private keys, or populated secret files. Use placeholders in tracked examples and documentation.
- Keep secrets out of logs, command output, and shared VS Code configuration. `.gitignore` is not a substitute for reviewing files before staging.
- Store local secret values in `.env`. Keep `.env.example` tracked with the required variable names and placeholder values only, never real secrets.
