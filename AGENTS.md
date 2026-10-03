# AGENTS.md

## Project overview

- Project brief: we are creating `[complete here]`.
- Planned stack: React Native for the frontend, Python with FastAPI for the backend, PostgreSQL for the database, and Docker with Docker Compose.
- Development environment: VS Code on macOS, Windows, and Linux. `.gitignore` should cover generated artifacts from the stack and development environments, as well as local secret files.

## Working rules

- Always use classic dashes (`-`) rather than em dashes in code, comments, documentation, commit messages, and responses.
- Follow the repository's existing code structure, formatting, commenting, and documentation style. Read nearby files before editing and use established tooling when available.
- Never delete comments written by the user. If a comment conflicts with a requested change, point out the conflict and ask the user how to resolve it. The only exception is a TODO comment addressed by your changes, which may be removed when replaced with the corresponding implementation.
- Add code comments only when needed. Keep them simple, straightforward, and idiomatic, without excessive formatting.
- Make only changes needed to complete the requested task. Report unrelated errors or improvement opportunities instead of fixing them without being asked.
- Inspect the working tree before editing and preserve unrelated or pre-existing changes.
- Challenge unclear requirements or assumptions. Ask the user for clarification before implementing an ambiguous decision rather than inventing behavior, architecture, or scope. Continue independent work that does not depend on the answer.
- Validate that changes are correct and do not break related behavior. Review the final diff, run relevant available checks, and report their results and any checks that could not be run. Use `[complete here]` for validation.
- Use `.gitkeep` to include otherwise empty directories in Git. Remove a directory's `.gitkeep` once it contains other tracked files.

## Architecture and repository layout

- `frontend/` contains the React Native application. It currently has only a `.gitkeep` placeholder.
- `backend/` contains the Python FastAPI application. It currently has only a `.gitkeep` placeholder.
- `db/migrations/` contains dbmate SQL migrations, with both `migrate:up` and `migrate:down` sections in each file. Dbmate writes the generated schema snapshot to `db/schema.sql`.
- `docker-compose.yml` defines the PostgreSQL database and the one-shot dbmate migration service.
- `.env` holds local environment values and is ignored by Git. `.env.example` documents the variables required by Docker Compose.
- `README.md` is the top-level project documentation.

## Validation

- Run `git diff --check` after changes and inspect changed and newly created files for unintended edits.
- For documentation changes, check grammar, Markdown structure, and affected links or table-of-contents anchors.
- For ignore-rule changes, check representative ignored and tracked paths with `git check-ignore`.
- For code or Docker changes, run the relevant configured formatting, build, test, and configuration checks, including checks for affected callers or services. Add or update regression tests when behavior changes warrant them.

## Secrets and local files

- Never commit real credentials, tokens, private keys, or populated secret files. Use placeholders in tracked examples and documentation.
- Keep secrets out of logs, command output, and shared VS Code configuration. `.gitignore` is not a substitute for reviewing files before staging.
- Store local secret values in `.env`. Keep `.env.example` tracked with the required variable names and placeholder values only, never real secrets.
