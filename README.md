# eHackYeah2026

A civic application for reporting issues, proposing citizen initiatives, and tracking their progress.

## Repository layout

```text
eHackYeah2026/
├── apps/
│   ├── web/                         # frontend workspace
│   └── api/                         # backend workspace
├── db/
│   ├── migrations/                  # dbmate SQL migrations
│   └── seeds/                       # reference data and the contacts workbook
├── tooling/
│   ├── scripts/                     # development commands
│   └── seed/                        # XLS importer and its Docker image
├── tests/
│   ├── e2e/                         # cross-application scenarios
│   └── fixtures/                    # shared behavioral examples
├── docker-compose.yaml              # database, migrations, and seed import
├── package.json                     # root commands and Bun workspaces
├── bun.lock
├── .env.example
├── AGENTS.md
└── TESTING.md
```

## Startup

From the repository root, start the database with:

```sh
docker compose up
```

Compose starts PostGIS, applies migrations, and imports the institution contacts workbook. Defaults are provided for local development; create `.env` from `.env.example` only if you want to override them. The importer image is built from `tooling/seed/Dockerfile` and installs dependencies from `tooling/seed/requirements.txt`.

## Development commands

Install Bun 1.4 or newer and Node.js 22.12 or newer, then run commands from the repository root:

| Command | Purpose |
| --- | --- |
| `bun install` | Install workspace dependencies. |
| `bun run setup` | Create missing `.env` and run application setup. |
| `bun run all` | Install, set up, and start web and API. |
| `bun run web` | Start the frontend. |
| `bun run api` | Start the database and seed services, then start the API. |

The current web workspace is a React/Vite scaffold. The API workspace is not implemented yet. Setup preserves `.env`. PostgreSQL is published on `127.0.0.1:POSTGRES_PORT`. Ctrl+C stops applications; the database remains running.

## Web application

```sh
bun install
bun run web
```

Open the local URL printed by Vite. Edit `apps/web/src/App.tsx` for the UI and `apps/web/src/index.css` for styles. Run web checks and build commands from its workspace:

```sh
cd apps/web
bun run typecheck
bun run build
bun run preview
```

The build output is written to `apps/web/dist`.

## Data model

Reports store their geographical point using PostGIS `geography(Point, 4326)`. Each report can optionally belong to one report group with a shared response. Photos are represented by rows in `report_photos`; each row stores a persistent `storage_key` that refers to a file managed by the API/storage layer. The workbook contains institution addresses, but no coordinates or boundary polygons.

See [TESTING.md](TESTING.md) for data import behavior and database validation.
