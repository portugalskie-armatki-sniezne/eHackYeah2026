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
│   └── api/                         # backend workspace
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
├── docker-compose.app.yaml          # api and web containers from published images
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

- Setup runs `uv sync` to install dependencies in `apps/api/.venv`. uv downloads Python 3.10 or newer if needed and reuses the environment on subsequent runs.
- API documentation is available at <http://127.0.0.1:8000/docs>. `GET /health` checks the application without querying PostgreSQL.
- Authenticated `POST /inference` accepts text, supplied classification questions, and an optional photo. Translation and classification use empty providers by default. See [connecting translation and Laya providers](apps/api/docs/inference.md).
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

#### Development Report Connection

[`devReports.ts`](apps/web/src/api/devReports.ts) is a temporary, local-development-only connection. It runs when `import.meta.env.DEV` is true and displays **Development test mode** in the application. Production builds, including builds deployed to the `dev` environment, disable this flow. The production form currently keeps new markers in browser memory.

Authentication is still required: the helper creates or signs in to the shared test account, obtains a JWT from `/auth/login`, and sends it as `Authorization: Bearer <token>`. It supplies a fixed test title and the `issue` category. Reports and image files are really saved, so use a development database. Vite proxies `/api` to `http://127.0.0.1:8000`; `API_PROXY_TARGET` in the root `.env` can select another local API.

To migrate the form to normal authenticated use:

1. Implement user sign-in and replace `getDevSession()` with the signed-in user's session, including expired-token handling.
2. Use [`createReportsApi`](apps/web/src/api/reports.ts) with that user's token and the title/category collected by the form. Replace the development-only save/load branches and remove the shared test account flow and labels.
3. Configure the deployed API URL with a same-origin proxy or CORS. The Vite development proxy is not included in the production build.

The existing report endpoints and database schema support this transition; switching authentication needs no new SQL migration. The target database must already have the current [`db/migrations`](db/migrations) applied, including user authentication fields and report categories. Authentication does not apply database migrations.

### Automated Deployment

1. Configure the GitHub environments `dev` and `prod` with `VITE_API_URL` (the backend URL included in the frontend build), `VITE_GOOGLE_CLIENT_ID` (the OAuth client ID for Google sign-in, also set as `GOOGLE_CLIENT_ID` in the environment's `.env`), and `DEPLOY_DIR` (the deployment directory on the target machine).
2. Copy `docker-compose.app.yaml` to `DEPLOY_DIR/docker-compose.yaml` and place the environment's `.env` alongside it. The database runs in a separate Compose project; `DB_NETWORK` selects its network (default `ehackyeah2026_default`) and `POSTGRES_HOST` selects its host (default `db`). Keep `.env` valid for both Compose and a shell script, with database credentials safe to use in a URL.
3. Use `[1] Deploy` in GitHub Actions to deploy `web` or `api` to `dev` or `prod`. Pushes to `main` deploy changed services to `dev`; changes to `db/migrations` deploy `api`. The workflow builds images from `apps/web/Dockerfile` and `apps/api/Dockerfile` and publishes them to `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-web` and `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-api`, tagged with the environment and `<environment>-<commit SHA>`.
4. The self-hosted runner updates `WEB_IMAGE_TAG` or `API_IMAGE_TAG` in `DEPLOY_DIR/.env`, pulls images, applies migrations before restarting `api`, and restarts the selected services. A failed migration leaves the previous API container running. Deployment does not import seed data. Keep self-hosted runners out of workflows triggered by pull requests.
5. After deploying `api`, run `[4] Seed` manually for `dev` or `prod` to import reference data from `db/seeds`. It waits for deployments to the same environment. Repeating the import preserves IDs and avoids duplicates; seed data overwrites manual edits, while records absent from the seed files remain in the database.
6. Run `[2] Release` manually to deploy both services to `prod`, then publish a Git tag and GitHub release. Versions use the UTC date and a daily counter, for example `v2026.10.03-1`.
7. The Compose template stores report photos in `/app/uploads` on the `api_uploads` volume, so they survive deployments. Update the copy in `DEPLOY_DIR` when the template changes.

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

See [TESTING.md](TESTING.md) for data import behavior and database validation.
