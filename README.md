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
bun run db
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
| `bun run db` | Start the database, apply migrations, and wait for seed import. |
| `bun run api` | Start the database and seed services, then start the API. |

The current web workspace is a React/Vite scaffold. The API workspace is not implemented yet; `bun run api` still starts the database. Both `bun run db` and `bun run api` require Docker with Compose running. The database command returns after seed import finishes and leaves PostgreSQL running. Setup preserves `.env`. PostgreSQL is published on `127.0.0.1:POSTGRES_PORT`. Ctrl+C stops applications; the database remains running.

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

## Shared agent skills

Repository-local skills live in `.agents/skills/` and are versioned with the
project. Teammates can use them from a repository checkout in Codex:

| Skill | Example request | Behavior |
| --- | --- | --- |
| [commit](.agents/skills/commit/SKILL.md) | `Use $commit to commit the staged changes.` | Review the complete staged snapshot, run relevant checks, and create a commit. Push only when explicitly requested. |
| [pr](.agents/skills/pr/SKILL.md) | `Use $pr to open a pull request for this branch.` | Review and push the committed branch, then create or update a GitHub PR against the repository's default branch unless another base is supplied. |
| [babysit](.agents/skills/babysit/SKILL.md) | `Use $babysit to take these changes to main.` | Commit task changes if needed, create or resume a draft PR, validate, and squash merge into main. |

All three skills require Git. The PR and babysit skills also require authenticated
GitHub access through a connected integration or the `gh` CLI. They follow `AGENTS.md`
and accept optional message hints or issue references. They do not require
installing personal global skills. Agents that support skill files can also read
the linked `SKILL.md` instructions directly.

## Data model

Reports store their geographical point using PostGIS `geography(Point, 4326)`. Reports are saved before classification, so `reports.master_report_id` can be `NULL`. After classification, the backend creates or links a master report. Master reports keep independent content, a shared status and response, and an optional responsible institution. Comments and likes belong to master reports. Photos are represented by rows in `report_photos`; each row stores a persistent `storage_key` that refers to a file managed by the API/storage layer. The workbook contains institution addresses, but no coordinates or boundary polygons.

See [TESTING.md](TESTING.md) for data import behavior and database validation.
