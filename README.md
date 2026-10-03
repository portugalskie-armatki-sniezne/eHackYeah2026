# eHackYeah2026 - pomożeMy

**pomożeMy** is a **unified platform** for **reporting local issues**, **proposing citizen initiatives**, and **tracking their progress**.
It aims to simplify communication with public institutions by using AI (deterministic classifiers and generative models) to identify the authority responsible for each report based on a database built from publicly available information about institutions. Each report can include GPS coordinates and photos to illustrate the problem.

![pomożeMy - changing your city without excessive bureaucracy](docs/teaser-en.png)

**[POLISH README | README PO POLSKU](README_pl.md)**

## Repository Layout

```text
eHackYeah2026/
├── apps/
│   ├── web/                         # frontend workspace
│   ├── api/                         # backend workspace
│   └── notify/                      # internal SMTP relay
├── db/
│   ├── migrations/                  # dbmate SQL migrations
│   └── seeds/                       # reference data and the contacts workbook
├── docs/
│   ├── teaser-en.png                # English project teaser
│   └── teaser-pl.png                # Polish project teaser
├── tooling/
│   └── seed/                        # XLS importer, mock data importer, and their Docker image
├── tests/
│   ├── e2e/                         # cross-application scenarios
│   └── fixtures/                    # shared behavioral examples
├── docker-compose.yaml              # database, migrations, and seed import
├── docker-compose.app.yaml          # api, web, and notify containers from published images
├── Taskfile.yml                     # development commands
├── mise.toml                        # pinned Bun, Task, and uv versions
├── setup-dev-env.sh                 # installs mise, pinned tools, and dependencies
├── package.json                     # Bun workspaces
├── bun.lock
├── .env.example
├── README.md                        # English documentation
├── README_pl.md                     # Polish documentation
├── AGENTS.md
└── TESTING.md
```

## Access

You can access the project at [hackyeah.jakubowskii.pl/#main](https://hackyeah.jakubowskii.pl/#main), at least during the HackYeah 2026 hackathon.

## Deployment

### Prerequisites

1. Install `Docker` with `Compose`. Keep Docker running.
2. Run the setup script from the repository root. The script installs [mise](https://mise.jdx.dev), the Bun, Task, and uv versions pinned in `mise.toml`, and runs `task setup` to install project dependencies. Restart your shell if prompted. On Windows, install mise manually, then run `mise install` and `task setup`.

   ```sh
   ./setup-dev-env.sh
   ```

   > `task setup` creates `.env` from `.env.example` if it is missing and preserves an existing file.

3. Review the database settings and replace the environment variable placeholders in `.env` with appropriate values and a random `JWT_SECRET` before starting the API. The generation command is included in `.env.example`.

### Startup

> Run all the commands from the repository root with mise activated in your shell; otherwise prefix them with `mise exec --`.

1. `task db`: Start only the database, migrations, and seed import.
2. `task api`: Start the database, apply migrations, import reference data, and start the API.
3. `task web`: Start the frontend.

> We recommend running `task web` and `task api` in separate terminals. The API is available at <http://127.0.0.1:8000>; Vite prints the frontend URL. Ctrl+C stops the application in that terminal; PostgreSQL remains running on `127.0.0.1:POSTGRES_PORT`.

> Database startup imports the local government office workbook and the official service entity snapshot. `task db` returns after seed import finishes.

> For demos, `docker compose run --rm mock-seeder` replaces mock users, reports, photos, and discussions in Kraków. See [mock demo data](TESTING.md#mock-demo-data) for details and demo accounts.

#### API Application

- Setup runs `uv sync --extra inference` to install dependencies in `apps/api/.venv` and downloads pinned Laya and Polish-English translation checkpoints into `apps/api/models` (about 1.1 GB, excluded from Git). The first run requires Git and internet access. Later runs reuse complete downloads. uv downloads Python 3.10 or newer if needed.
- API documentation is available at <http://127.0.0.1:8000/docs>. `GET /health` checks the application without querying PostgreSQL.
- Saving a report or changing its coordinates requires access to `https://uldk.gugik.gov.pl/` to identify its municipality and county in Małopolskie. If the service is unavailable, the API returns an error so the user can retry.
- Authenticated `POST /inference` accepts text, supplied classification questions, and an optional photo. `POST /inference/service-entity` classifies a title, description, and optional photo into one service entity type. The model paths in `.env.example` enable local inference. For an existing `.env`, add `LAYA_MODEL_PATH=models/laya-vision` and `TRANSLATION_MODEL_PATH=models/opus-mt-pl-en`; setup preserves existing values. See [model setup and provider configuration](apps/api/docs/inference.md).
- Changes under `apps/api/app` reload the API automatically.
- Run `task be:lint` to check the API with Ruff, or `task be:lint:fix` to apply fixes and formatting.

#### Web Application

1. Edit `apps/web/src/App.tsx` for the UI and `apps/web/src/index.css` for styles. Run `task fe:lint` to check ESLint and Prettier, or `task fe:lint:fix` to apply fixes and formatting.
2. Run checks and build commands from the web workspace:

   ```sh
   cd apps/web
   bun run typecheck
   bun run build
   bun run preview
   ```

3. The build output is written to `apps/web/dist`.

#### Report Connection

The map loads pins from `GET /master-reports` and files new reports with `POST /reports` through [`reports.ts`](apps/web/src/api/reports.ts). Every request goes through `apiFetch` in [`client.ts`](apps/web/src/api/client.ts), which adds the stored token and drops it on a 401. Reading reports, masters and categories needs no token. Filing a report needs the signed-in session from [`session.ts`](apps/web/src/api/session.ts); signed out, adding a marker opens the sign-in dialog. The form has no title or category field yet, so the title is taken from the start of the description and the category is `issue`. Reports and image files are really saved, so use a development database.

In development Vite proxies `/api` to `http://127.0.0.1:8000`; `API_PROXY_TARGET` in the root `.env` can select another local API. Deployed builds get the API origin from `VITE_API_URL` at build time, so configure a same-origin proxy or CORS there.

### Automated Deployment

1. Configure the GitHub environments `dev` and `prod` with `VITE_API_URL` (the backend URL included in the frontend build), `VITE_GOOGLE_CLIENT_ID` (the OAuth client ID for Google sign-in, also set as `GOOGLE_CLIENT_ID` in the environment's `.env`), and `DEPLOY_DIR` (the deployment directory on the target machine).
2. Copy `docker-compose.app.yaml` to `DEPLOY_DIR/docker-compose.yaml` and place the environment's `.env` alongside it. The database runs in a separate Compose project; `DB_NETWORK` selects its network (default `ehackyeah2026_default`) and `POSTGRES_HOST` selects its host (default `db`). Keep `.env` valid for both Compose and a shell script, with database credentials safe to use in a URL. Configure Gmail and test delivery for `notify` using the [mail setup instructions](apps/notify/docs/deployment.md).
3. Use `[1] Deploy` in GitHub Actions to deploy `web`, `api`, `notify`, or `all` of them at once to `dev` or `prod`. Pushes to `main` deploy changed services to `dev`; changes to `db/migrations` deploy `api`. The workflow builds images from `apps/web/Dockerfile`, `apps/api/Dockerfile`, and `apps/notify/Dockerfile` and publishes them to `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-web`, `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-api`, and `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-notify`, tagged with the environment and `<environment>-<commit SHA>`.
4. The self-hosted runner updates `WEB_IMAGE_TAG`, `API_IMAGE_TAG`, or `NOTIFY_IMAGE_TAG` in `DEPLOY_DIR/.env`, pulls images, applies migrations before restarting `api`, and restarts the selected services. A failed migration leaves the previous API container running. Deployment does not import seed data. Keep self-hosted runners out of workflows triggered by pull requests.
5. After deploying `api`, run `[4] Seed` manually for `dev` or `prod` to import reference data from `db/seeds`. It waits for deployments to the same environment. Repeating the import preserves IDs and avoids duplicates; seed data overwrites manual edits, while records absent from the seed files remain in the database.
6. Run `[2] Release` manually to deploy all three services to `prod`, then publish a Git tag and GitHub release. Versions use the UTC date and a daily counter, for example `v2026.10.03-1`.
7. The Compose template stores report photos in `/app/uploads` on the `api_uploads` volume, so they survive deployments. `notify` mounts the same volume read-only to attach photos to emails. Update the copy in `DEPLOY_DIR` when the template changes.

> `[3] Lint` runs ESLint, Prettier, and Ruff on every pull request and push to `main`, using GitHub-hosted runners.

## Shared Agent Skills

Repository-local skills live in `.agents/skills/` and are versioned with the
project. Teammates can use them from a repository checkout in Codex:

| Skill                                      | Example request                                   | Behavior                                                                                                                                         |
| ------------------------------------------ | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| [commit](.agents/skills/commit/SKILL.md)   | `Use $commit to commit the staged changes.`       | Review the complete staged snapshot, run relevant checks, and create a commit. Push only when explicitly requested.                              |
| [pr](.agents/skills/pr/SKILL.md)           | `Use $pr to open a pull request for this branch.` | Review and push the committed branch, then create or update a GitHub PR against the repository's default branch unless another base is supplied. |
| [babysit](.agents/skills/babysit/SKILL.md) | `Use $babysit to take these changes to main.`     | Commit task changes if needed, create or resume a draft PR, validate, and squash merge into main.                                                |

All three skills require Git. The PR and babysit skills also require authenticated
GitHub access through a connected integration or the `gh` CLI. They follow `AGENTS.md`
and accept optional message hints or issue references. They do not require
installing personal global skills. Agents that support skill files can also read
the linked `SKILL.md` instructions directly.

## Data Model

- Reports store their location using PostGIS `geography(Point, 4326)`. They are saved before classification, so `reports.master_report_id` can be `NULL`. After classification, the backend creates or links a master report.
- Master reports keep independent content, a shared status and response, and an optional responsible institution. Comments and likes belong to master reports.
- Photos are represented by rows in `report_photos`. Each row stores a persistent `storage_key` that refers to a file managed by the API or storage layer.
- The workbook contains institution addresses, but no coordinates or boundary polygons.
- New reports are accepted only in Małopolskie and store the TERYT codes and names of their municipality and county, determined from their coordinates using [GUGiK's PRG boundaries](https://uldk.gugik.gov.pl/opis.html). Existing reports keep these fields empty until their location is updated. The administrative area does not determine the institution responsible for the issue.

See [TESTING.md](TESTING.md) for data import behavior and database validation.
