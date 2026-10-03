# eHackYeah2026

A web application for reporting civic issues, proposing citizen initiatives, and tracking their progress.

## Repository layout

```text
eHackYeah2026/
├── apps/
│   ├── web/                 # minimal React + Vite + TypeScript frontend
│   └── api/                 # backend workspace, application not implemented yet
├── db/
│   ├── migrations/          # existing dbmate SQL migrations
│   └── seeds/               # development and reference data
├── infra/
│   └── compose.yaml         # PostgreSQL and dbmate
├── tooling/
│   └── scripts/             # development and maintenance scripts
├── tests/
│   ├── e2e/                 # cross-application scenarios
│   └── fixtures/            # shared behavioral examples
├── .agents/
│   └── skills/              # repository-local agent skills
├── .github/
│   └── workflows/           # future CI workflows
├── package.json             # root commands and Bun workspaces
├── bun.lock                 # JavaScript dependency lockfile
├── .env.example
├── .gitignore
├── AGENTS.md
├── README.md
└── TESTING.md
```

## Development commands

Install Bun 1.4 or newer and Node.js 22.12 or newer, then run commands from the repository root:

| Command | Purpose |
| --- | --- |
| `bun install` | Install workspace JavaScript dependencies. |
| `bun run setup` | Create missing `.env` and run application setup. |
| `bun run all` | Install, set up, and start web and API. |
| `bun run web` | Start the frontend. |
| `bun run api` | Start PostgreSQL, apply migrations, and start the API. |

The web application is ready to run. The API is not implemented yet and is skipped.
Setup preserves `.env`.
Configured API startup requires Docker with Compose; PostgreSQL uses
`127.0.0.1:POSTGRES_PORT`. Ctrl+C stops applications; PostgreSQL remains running.

Future applications provide `scripts.dev` and, when needed, `scripts.setup` in
their workspace manifests. API setup installs Python dependencies. Scripts run
from their application directory with root `.env` values. Keep setup repeatable,
servers in the foreground, and reloads scoped to each application.

## Web application

```sh
bun install
bun run web
```

Open the local URL printed by Vite. Edit `apps/web/src/App.tsx` for the UI and
`apps/web/src/index.css` for styles. `apps/web/src/main.tsx` mounts the application.

Run web checks and production commands from its workspace:

```sh
cd apps/web
bun run typecheck
bun run build
bun run preview
```

The build output is written to `apps/web/dist`.

## Shared agent skills

Repository-local skills live in `.agents/skills/` and are versioned with the
project. Teammates can use them from a repository checkout in Codex:

| Skill | Example request | Behavior |
| --- | --- | --- |
| [commit](.agents/skills/commit/SKILL.md) | `Use $commit to commit the staged changes.` | Review the complete staged snapshot, run relevant checks, and create a commit. Push only when explicitly requested. |
| [pr](.agents/skills/pr/SKILL.md) | `Use $pr to open a pull request for this branch.` | Review and push the committed branch, then create or update a GitHub PR against the repository's default branch unless another base is supplied. |

The commit skill requires Git. The PR skill also requires authenticated GitHub
access through a connected integration or the `gh` CLI. Both follow `AGENTS.md`
and accept optional message hints or issue references. They do not require
installing personal global skills. Agents that support skill files can also read
the linked `SKILL.md` instructions directly.
