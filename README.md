# eHackYeah2026 - pomożeMy

**pomożeMy** is a **unified platform** for **reporting local issues**, **proposing citizen initiatives**, and **tracking their progress**.
It aims to simplify communication with public institutions by using AI (deterministic classifiers and generative models) to identify the authority responsible for each report based on a database built from publicly available information about institutions. Each report can include GPS coordinates and photos to illustrate the problem.

**[POLISH README | README PO POLSKU](README_pl.md)**

![pomożeMy - changing your city without excessive bureaucracy](docs/teaser-en.png)

## Repository Layout

```text
eHackYeah2026/
├── apps/
│   ├── web/                         # frontend workspace
│   ├── api/                         # backend workspace
│   ├── notify/                      # internal SMTP relay
│   └── gemini/                      # internal initiative visualization connector
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
├── docker-compose.app.yaml          # api, web, notify, and gemini containers from published images
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

## Access and Environments

The platform is deployed and publicly accessible:

- **Production environment (`prod`)**: Available at [hackyeah.jakubowskii.pl/#main](https://hackyeah.jakubowskii.pl/#main) with Google OAuth integration, production database, geocoded institutions, and the ROPS social innovations database.
- **Development environment (`dev`)**: Continuously updated on pushes to `main` via GitHub Actions for verifying changes and integrating new features.

To test the application, you can sign in with the demo account:
- **Email**: `user@mock.ehackyeah.pl`
- **Password**: `mock_demo_password`

Both environments run three containerized services configured via Docker Compose:
- **`web`**: Single-page application built with React, Vite, TypeScript, and MapLibre GL JS.
- **`api`**: REST API backend built with FastAPI, PostgreSQL, PostGIS, and pgvector.
- **`notify`**: Internal mail relay microservice sending email notifications to institutions using Markdown templates and Gmail SMTP.

## Core Features

- **Interactive Map and Geolocation**: Explore local reports and initiatives clustered on an interactive map. Center view on user GPS location, drop pins at exact coordinates, and inspect active issues.
- **Civic Reporting and Master Grouping**: File issues or civic initiatives with descriptions, photos, and coordinates. The API automatically clusters similar nearby reports into shared master reports to prevent duplicate municipal tickets.
- **Administrative Assignment**: Automatic identification of municipalities and counties in Małopolskie via the GUGiK ULDK service.
- **Institution Routing and Recommendation**: Match reports to competent public offices or municipal service entities using AI classification (Laya Vision) and nearest geocoded seat locations.
- **ROPS Social Innovations Catalog**: Explore and search the Regional Center for Social Policy (ROPS) catalog of proven social initiatives. Features hybrid search combining vector embeddings (cosine similarity) and Polish stemming with dynamic relevance scoring.
- **Official Mail Notifications**: Internal relay transforms verified issues and initiatives into structured official notifications and sends them directly to competent offices with photos and Google Maps links.
- **Interactive Onboarding Tour**: Guided workflow walkthrough for new residents offering automated animation with simulated pointer movement or manual step-by-step guidance across map exploration, issue reporting, notifications, and social innovations, with zero production side effects.
- **Authentication and Profiles**: Sign in using email/password or Google SSO, manage user profile, and track filed reports and comments.
- **Bilingual Interface**: Full Polish and English language localization with on-the-fly switching.

## Deployment

### Prerequisites

1. Install `Docker` with `Compose`. Keep Docker running.
2. Run the setup script from the repository root. The script installs [mise](https://mise.jdx.dev), the Bun, Task, and uv versions pinned in `mise.toml`, and runs `task setup` to install project dependencies. Restart your shell if prompted. On Windows, install mise manually, then run `mise install` and `task setup`.

   ```sh
   ./setup-dev-env.sh
   ```

   > `task setup` creates `.env` from `.env.example` if it is missing and preserves an existing file.
   > `task setup`, `task web`, `task db`, and `task api` enable the pre-commit hook from `.githooks`, which runs `task fe:lint` or `task be:lint` when a commit changes `apps/web` or `apps/api`.

3. Review the database settings and replace the environment variable placeholders in `.env` with appropriate values and a random `JWT_SECRET` before starting the API. The generation command is included in `.env.example`.

### Startup

> Run all the commands from the repository root with mise activated in your shell; otherwise prefix them with `mise exec --`.

1. `task db`: Start only the database, migrations, and seed import.
2. `task api`: Start the database, apply migrations, import reference data, and start the API.
3. `task web`: Start the frontend.

> We recommend running `task web` and `task api` in separate terminals. The API is available at <http://127.0.0.1:8000>; Vite prints the frontend URL. Ctrl+C stops the application in that terminal; PostgreSQL remains running on `127.0.0.1:POSTGRES_PORT`.

> Database startup imports the local government office workbook, the reviewed service entity and seat snapshots, and the ROPS social innovation library shown on the initiatives page. `task db` returns after seed import finishes.

> For demos, `docker compose run --rm mock-seeder` replaces mock users, reports, photos, and discussions in Kraków. You can sign in using `user@mock.ehackyeah.pl` with password `mock_demo_password`. See [mock demo data](TESTING.md#mock-demo-data) for details and demo accounts.

#### API Application

- Setup runs `uv sync --extra inference` to install dependencies in `apps/api/.venv` and downloads pinned Laya and Polish-English translation checkpoints into `apps/api/models` (about 1.1 GB, excluded from Git). The first run requires Git and internet access. Later runs reuse complete downloads. uv downloads Python 3.10 or newer if needed.
- API documentation is available at <http://127.0.0.1:8000/docs>. `GET /health` checks the application without querying PostgreSQL.
- Saving a report or changing its coordinates requires access to `https://uldk.gugik.gov.pl/` to identify its municipality and county in Małopolskie. If the service is unavailable, the API returns an error so the user can retry.
- Authenticated `POST /inference` accepts text, supplied classification questions, and an optional photo. `POST /inference/service-entity` classifies a title, description, and optional photo into one service entity type. The model paths in `.env.example` enable local inference. For an existing `.env`, add `LAYA_MODEL_PATH=models/laya-vision` and `TRANSLATION_MODEL_PATH=models/opus-mt-pl-en`; setup preserves existing values. See [model setup and provider configuration](apps/api/docs/inference.md).
- Changes under `apps/api/app` reload the API automatically.
- Run `task be:lint` to check the API with Ruff, or `task be:lint:fix` to apply fixes and formatting.

#### Gemini Connector

`apps/gemini` is an internal image-generation service for `improvement` reports. Gemini Flash prepares a prompt from the description and photos; Nano Banana generates one visualization. The main API handles authenticated requests before and after publication, user limits, background jobs, and persistent image history. It also sends one test email for each new case, always to the configured test address, including on prod during the hackathon. See the [backend integration contract](apps/api/docs/visualizations.md) and the [Gemini API guide](apps/gemini/docs/api.md).

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

The notifications page reads `GET /notifications` through [`notifications.ts`](apps/web/src/api/notifications.ts), which also keeps the navbar's unread count. Each notification carries the buttons that act on it: open the case, mark it read, dismiss it, and for an offered photo take it or turn it down through [`photoProposals.ts`](apps/web/src/api/photoProposals.ts). "Open the case" points the hash at one master, as `#map/<master id>`, and the map opens that pin's sheet.

A case with no photo shows the way to offer one, on the map's sheet and on the reports page. Until the case's author takes it, the offered photo stands in for the case's picture under a question mark, on the pin and in both sheets.

In development Vite proxies `/api` to `http://127.0.0.1:8000`; `API_PROXY_TARGET` in the root `.env` can select another local API. Deployed builds get the API origin from `VITE_API_URL` at build time, so configure a same-origin proxy or CORS there.

### Automated Deployment

1. Configure the GitHub environments `dev` and `prod` with `VITE_API_URL` (the backend URL included in the frontend build), `VITE_GOOGLE_CLIENT_ID` (the OAuth client ID for Google sign-in, also set as `GOOGLE_CLIENT_ID` in the environment's `.env`), and `DEPLOY_DIR` (the deployment directory on the target machine).
2. Create `DEPLOY_DIR` on the target machine and place the environment's `.env` in it. Set `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`, copy the service-account JSON to the deployment host, and set `GEMINI_CREDENTIALS_FILE` to its path relative to `docker-compose.yml` (default `./project-key.json`). Set `GEMINI_UID` and `GEMINI_GID` to the numeric output of `id -u` and `id -g` for the account that owns the file, so the unprivileged container can read it. Keep the credentials file private and outside Git. The database runs in a separate Compose project; `DB_NETWORK` selects its network (default `ehackyeah2026_default`) and `POSTGRES_HOST` selects its host (default `db`). Keep `.env` valid for both Compose and a shell script, with database credentials safe to use in a URL. Configure Gmail and test delivery for `notify` using the [mail setup instructions](apps/notify/docs/deployment.md).
3. Use `[1] Deploy` in GitHub Actions to deploy `web`, `api`, `notify`, `gemini`, or all of them to `dev` or `prod`. Pushes to `main` deploy changed services to `dev`; changes to `db/migrations` deploy `api`. The workflow builds images from the four service Dockerfiles and publishes them to `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-web`, `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-api`, `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-notify`, and `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-gemini`, tagged with the environment and `<environment>-<commit SHA>`.
4. The self-hosted runner copies `docker-compose.app.yaml` to `DEPLOY_DIR/docker-compose.yml`, updates the selected service's `*_IMAGE_TAG` in `DEPLOY_DIR/.env`, pulls images, applies migrations before restarting `api`, and restarts the selected services. A failed migration leaves the previous API container running. Deployment does not import seed data. Keep self-hosted runners out of workflows triggered by pull requests.
5. After deploying `api`, run `[4] Seed` manually for `dev` or `prod` to import reference data from `db/seeds`. It waits for deployments to the same environment. Repeating the import preserves IDs and avoids duplicates; seed data overwrites manual edits, while records absent from the seed files remain in the database.
6. Run `[2] Release` manually to deploy all four services to `prod`, then publish a Git tag and GitHub release. Versions use the UTC date and a daily counter, for example `v2026.10.03-1`.
7. The Compose template stores report photos in `/app/uploads` on the `api_uploads` volume, so they survive deployments. `notify` and `gemini` mount the same volume read-only.

The API image includes CPU inference dependencies and pinned Laya and PL-to-EN translation models. GitHub Actions downloads the models in a cached image layer and checks real Polish classification with and without an image during the build, without network access. Compose enables them on both dev and prod without additional server configuration. The container runs `API_WORKERS` processes (default 2), and each loads its own copy of the models. API startup repeats the text check and reports readiness at `/ready` only after it succeeds. Deployment waits up to 10 minutes for readiness; a model failure fails the deployment. See [inference deployment](apps/api/docs/inference.md#wdrożenie-na-vps).

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
- A master report with no photo can be offered one by any signed-in resident. The offer waits in `master_report_photo_proposals` under a question mark until the resident who filed the case first takes it, which files the picture as a report photo, or turns it down, which deletes the file.
- `notifications` records what happened to a case its recipient filed, commented on, or offered a photo for: the case taken up or finished, an office's update, a new comment, and an offered photo with its decision.
- The workbook contains institution addresses, but no coordinates or boundary polygons.
- New reports are accepted only in Małopolskie and store the TERYT codes and names of their municipality and county, determined from their coordinates using [GUGiK's PRG boundaries](https://uldk.gugik.gov.pl/opis.html). Existing reports keep these fields empty until their location is updated. The administrative area does not determine the institution responsible for the issue.

See [TESTING.md](TESTING.md) for data import behavior and database validation.
