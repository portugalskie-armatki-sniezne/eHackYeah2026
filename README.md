# eHackYeah2026

A web application for reporting civic issues, proposing citizen initiatives, and tracking their progress.

## Repository layout

```text
eHackYeah2026/
├── apps/
│   ├── web/                 # frontend workspace, application not implemented yet
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

Install Bun 1.4 or newer, then run commands from the repository root:

| Command | Purpose |
| --- | --- |
| `bun install` | Install workspace JavaScript dependencies. |
| `bun run setup` | Create missing `.env` and run application setup. |
| `bun run all` | Install, set up, and start web and API. |
| `bun run web` | Start the frontend. |
| `bun run api` | Start PostgreSQL, apply migrations, and start the API. |

Applications are not implemented yet and are skipped. Setup preserves `.env`.
Configured API startup requires Docker with Compose; PostgreSQL uses
`127.0.0.1:POSTGRES_PORT`. Ctrl+C stops applications; PostgreSQL remains running.

Future applications provide `scripts.dev` and, when needed, `scripts.setup` in
their workspace manifests. API setup installs Python dependencies. Scripts run
from their application directory with root `.env` values. Keep setup repeatable,
servers in the foreground, and reloads scoped to each application.
