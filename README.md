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
│   └── seed/                        # XLS importer and its Docker image
├── tests/
│   ├── e2e/                         # cross-application scenarios
│   └── fixtures/                    # shared behavioral examples
├── docker-compose.yaml              # database, migrations, and seed import
├── Taskfile.yml                     # development commands
├── mise.toml                        # pinned Bun, Task, and uv versions
├── setup-dev-env.sh                 # installs mise, pinned tools, and dependencies
├── package.json                     # Bun workspaces
├── bun.lock
├── .env.example
├── AGENTS.md
└── TESTING.md
```

## Startup

From the repository root, start the database with:

```sh
task db
```

Compose starts PostGIS, applies migrations, and imports the institution contacts workbook. Defaults are provided for local development; create `.env` from `.env.example` only if you want to override them. The importer image is built from `tooling/seed/Dockerfile` and installs dependencies with uv from `tooling/seed/pyproject.toml` and `tooling/seed/uv.lock`.

## Development commands

Install Node.js 22.12 or newer and Docker with Compose, then set up the environment from the repository root:

```sh
./setup-dev-env.sh
```

The script installs [mise](https://mise.jdx.dev) when it is missing, installs the Bun, Task, and uv versions pinned in `mise.toml`, and runs `task setup`. Restart your shell when the script asks for it. On Windows, install mise manually, then run `mise install` and `task setup` instead.

Commands are defined in `Taskfile.yml` and need mise activated in your shell; otherwise prefix them with `mise exec --`. Run them from the repository root:

| Command | Purpose |
| --- | --- |
| `task setup` | Install JavaScript, TypeScript, and Python dependencies, and create missing `.env`. |
| `task web` | Start the frontend. |
| `task db` | Start the database, apply migrations, and wait for seed import. |
| `task api` | Start the database and seed services, then start the API. |

The current web workspace is a React/Vite scaffold. The API workspace is a FastAPI placeholder. Web and API start separately, so run `task web` and `task api` in separate terminals. Both `task db` and `task api` require Docker with Compose running. The database command returns after seed import finishes and leaves PostgreSQL running. Setup preserves `.env`. PostgreSQL is published on `127.0.0.1:POSTGRES_PORT`. Ctrl+C stops applications; the database remains running.

## API application

```sh
task setup
task api
```

Setup runs `uv sync`, which creates `apps/api/.venv` and installs Python dependencies from `apps/api/pyproject.toml` and `apps/api/uv.lock`. uv downloads Python 3.10 or newer when none is available. Repeating setup reuses the virtual environment. The API starts after migrations and seed import finish, at <http://127.0.0.1:8000>. The placeholder provides `GET /` and `GET /health`, with interactive API documentation at <http://127.0.0.1:8000/docs>. The health endpoint checks the application only; it does not query PostgreSQL. Edit `apps/api/app/main.py`; changes under `apps/api/app` reload the API automatically.

## Web application

```sh
task setup
task web
```

Open the local URL printed by Vite. Edit `apps/web/src/App.tsx` for the UI and `apps/web/src/index.css` for styles. Run web checks and build commands from its workspace:

```sh
cd apps/web
bun run typecheck
bun run build
bun run preview
```

The build output is written to `apps/web/dist`.

## Deployment

The `[1] Deploy web` workflow builds and pushes the web image, then deploys it to one environment:

| Trigger | Environment |
| --- | --- |
| Push to `main` that changes the frontend. | `dev` |
| Manual run from the Actions tab. | `dev` or `prod`, chosen when starting the run. |

The web image is built from `apps/web/Dockerfile` with the repository root as the build context and pushed to `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-web`. Builds are tagged with the environment name and with `<environment>-<commit SHA>`, for example `dev` and `dev-<commit SHA>`. To build the image locally, run `docker build -f apps/web/Dockerfile -t ehackyeah-web .` from the repository root.

The workflow reads its configuration from the GitHub environments `dev` and `prod`. Each environment needs two variables: `VITE_API_URL`, the backend URL that Vite inlines into the frontend bundle, and `DEPLOY_DIR`, the directory with the Compose file on the target machine. Deployment runs `docker compose pull` and `docker compose up -d` on a self-hosted runner labeled `dev` or `prod`. Do not use these runners in workflows triggered by pull requests, because the repository is public.

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
