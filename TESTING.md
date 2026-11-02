# Database startup and validation

From the repository root, run:

```sh
task db
```

The command starts Compose services from the root `docker-compose.yaml` and waits for seed import to finish. PostgreSQL stays running afterward. Compose provides local defaults; `.env` is optional.
The seed image uses `tooling/seed/Dockerfile`, `tooling/seed/pyproject.toml`, and `tooling/seed/uv.lock`.
To inspect migration and import output, run `docker compose logs db-migrator db-seeder`.

Startup waits for PostgreSQL, applies dbmate migrations, then imports
`db/seeds/teleaddr_base_16042026.xls` into `local_government_offices` and
`db/seeds/service_entities.json` into `service_entities`. The XLS importer requires the source's 22 headers,
normalizes numeric cells and blank values, and upserts contacts by their seven-digit
TERYT code in one transaction. Repeated runs preserve IDs and unchanged rows. Source
updates replace the corresponding contact fields; contacts absent from the workbook
are retained. Polish source values are preserved; database identifiers are English. The three fax
fields are validated as part of the source layout but are not stored. Both datasets
are validated before writing and imported in one transaction.

The same run imports `db/seeds/rops_projects.json` into `projects` and `project_chunks`
when the file is present. The snapshot holds the social innovation library of ROPS
Kraków, collected from the category and innovation pages of
<https://rops.krakow.pl/innowacje-spoleczne/biblioteka-innowacji-spolecznych> by
`tooling/seed/collect_projects.py`. Each innovation keeps its library slug, category,
page address, lead, and the numbered sections of its page. Projects are upserted by slug;
their chunks, one per section, are written afresh. Refresh the snapshot with
`python3 tooling/seed/collect_projects.py` from the repository root.

The PostGIS image keeps PostgreSQL 18 and the `/var/lib/postgresql` volume path.
The upstream image supports amd64, so ARM machines need Docker's amd64 emulation.
These edited initial migrations target a fresh database. If versions 01-03 were already
applied, dbmate will not replay them; preserve existing data with a forward migration
before using the new schema. Do not delete an existing volume to apply these edits.

Run the database checks with Docker running:

```sh
python3 tests/check_database.py
```

This builds the importer and creates a uniquely named Compose project with test
credentials and a separate database volume. It checks startup ordering, all 203 office
records and the complete service entity snapshot, repeat startup, XLS/XML/JSON validation,
BIP filtering, distinct transport roles, stable IDs, atomic upserts, spatial
distance queries, reports saved before classification, master report links and independent
content, statuses, assignment to either an office or a service entity, exclusive assignment,
referenced entity deletion restrictions, shared comments and likes, photo relationships,
visualization attempt cleanup, edit timestamps, the innovation library import, the one
waiting photo proposal per master with its decision date, notification kinds and their
cascades, visualization and delivery queue tables, and reference data rollback.
All migrations are rolled back and reapplied. Its containers, volume, and local
image tag are removed afterward.

Report locations use `geography(Point, 4326)`. Supply longitude before latitude, for
example `ST_SetSRID(ST_MakePoint(19.94, 50.06), 4326)::geography`. Validate longitude
within -180 to 180 and latitude within -90 to 90 in the API before inserting; PostGIS
geography can normalize out-of-range inputs. `ST_DWithin` uses meters with this type.
The institution workbook contains addresses, but no coordinates or boundary polygons.

Reports are saved before classification, with no master assigned. The backend then
creates a master from the first report or links the report to an existing master.
Master content is independent of individual reports; statuses and responsible institutions
belong to masters. `responsible_office_id` and `responsible_service_entity_id` have
separate foreign keys; at most one can be set. Both can be NULL before assignment.
Referenced offices and entities cannot be deleted. Comments and likes also belong to masters. Categories and statuses
are populated by migration 04. Each photo row contains a persistent storage key;
the API/storage layer owns file upload, access,
and deletion. Deleting a report removes its photo rows and preserves its master and
the shared discussion. A master with linked reports cannot be deleted.
`users.edited_at`, `reports.edited_at`, and `master_reports.edited_at` are maintained
by database triggers. Users must provide at least one nonblank email or phone number;
email and phone are unique. `users.role` is `user`, `office`, or `admin` and defaults
to `user`. The API must store a complete encoded password hash (including its salt)
in `users.password_hash`. An account needs a password hash, a linked Google account in
the unique `users.google_sub`, or both.

Migrations 01 and 02 create the tables, migration 03 adds constraints, and migration
04 inserts the initial categories (`improvement`, `issue`) and master report statuses.
Migration 05 adds Google sign-in to users; its rollback gives accounts without a password
the hash `!`, which no password matches.
Migration 07 adds persistent institution seat coordinates, their municipality code,
the geocoding timestamp, and the source address. API tests cover geocoding updates,
unchanged addresses, stale coordinates, and administrative recommendation priority.
External geocoding is mocked in these tests.
Migration 11 marks office and admin comments as highlighted. Migration 10 creates the
ROPS innovation library tables `projects` and `project_chunks`, with a `polish` text search
configuration copied from `simple` for the chunk index, and adds pgvector embedding columns
only when the database image ships the extension; the PostGIS image does not.
Migration 12 creates `master_report_photo_proposals` and `notifications`. A partial unique
index allows one waiting proposal per master, and a check keeps `decided_at` set exactly
when the state is not `pending`; a decided proposal frees the master for another photo.
Notifications belong to their recipient and go with the user, master, or proposal they
point at.
The statuses mean: `created` is saved in the application, `reported` is successfully
sent to the responsible institution, `inprogress` has confirmed work in progress,
and `finished` has confirmed completion. The backend owns classification, master
creation and assignment, and status transitions.

## API tests

Start the database with `task db`, then run the API tests from their workspace:

```sh
cd apps/api
uv run pytest
```

The test configuration loads the repository's `.env` before importing the application.
Existing environment variables take precedence. This keeps plain `pytest` runs on the
same configured database as the API, rather than silently using the local defaults.
Each database test rolls back its transaction; photo files use temporary directories.
Database tests are skipped when the configured database is unavailable.

The workflow tests replace the Gemini and notify HTTP calls. They cover draft and
published generation, private files, image history, publication during generation,
idempotency, limits, leases after restart, file errors, draft cleanup, and one test mail
per new master. No Google generation or SMTP delivery is performed. The concurrency
test uses a temporary schema with separate committed connections and removes it afterward.

Run the integration checks with the migrated database available:

```sh
cd apps/api
uv run pytest tests/test_workflows.py tests/test_reports.py tests/test_master_matching.py tests/test_master_reports.py tests/test_inference_startup.py
```

The notify and Gemini suites also replace their providers. Run `uv run pytest` in
each workspace. See the [frontend contract](apps/api/docs/visualizations.md) for the
new endpoints and the mandatory hackathon test destination, including on prod.

## Mock demo data

To show the application with data, run from the repository root:

```sh
docker compose run --rm mock-seeder
```

The `mock-seeder` service uses the `mock` profile, so `docker compose up` and `task db`
do not start it. It waits for `db-seeder`, then runs `tooling/seed/populate_mock_data.py`
with content from `tooling/seed/mock_data.py`. It creates 30 users, 63 master reports
in Kraków with 136 reports, comments, and likes over the last 90 days. Hand-written
scenarios at known places are combined with reports generated from topic templates
with a fixed random seed. Reports of one master lie within 25 meters and share the
master's category, so they stay consistent with the API matching. Older masters have
further statuses; from `reported` on, they are assigned to the matching Kraków service
entity, such as ZDMK, ZZM, MPO, or ZTP, or to the city office.

Report photos are AI-generated images from `tooling/seed/mock_photos/`. They are
written to `apps/api/uploads`, the default `UPLOAD_DIR` of `task api`. The container
runs as root and gives new files the owner of `apps/api`.

All mock users have `@mock.ehackyeah.pl` emails. Each run deletes them together with
their reports, photos, comments, likes, and masters left without reports, then inserts
the data again in one transaction. Other users and their data are kept. The demo
accounts `user@mock.ehackyeah.pl`, `office@mock.ehackyeah.pl`, and
`admin@mock.ehackyeah.pl` have the roles `user`, `office`, and `admin`. All mock users
share the local demo password `mock_demo_password`, stored as a fixed argon2 hash.

## Reference data import and refresh

The [data model](apps/api/docs/data-model.md#źródła-danych) lists official sources,
including the MSWiA office workbook. Normal `task db` startup imports the tracked
workbook and service entity JSON without fetching external sources. The office, institution and reviewed seat imports
run in one transaction. COPY and advisory-locked upserts preserve IDs and unchanged
rows; records absent from a later source are retained.

To refresh service entities, run the collector with Python 3.14 from the repository root:

```sh
python3 tooling/seed/collect_service_entities.py db/seeds/service_entities.json --supplements db/seeds/service_entities_supplements.json
```

The collector reads the central BIP ZIP first, then the regional BIP API. It searches
ten name fragments, follows start articles and up to two contact menu entries,
and excludes archived articles and editor contacts. It parses contact HTML only
where the API does not provide structured fields. Matching BIP URLs and reviewed
aliases merge duplicates. Reviewed supplements supply missing entities and contacts.

Review the JSON diff and supplements before running `task db`. The collector validates
the result before replacing the snapshot. Network errors abort the refresh, except
optional pages returning 404, which are recorded in `omissions`. The current PUK
Zielonki start-page omission is covered by its separate contact article.

For offline reproduction, use `--bip-export` with a saved ZIP/XML, `--regional-units`
with saved search results, or `--cache-dir` for API responses. These require
`--verified-on YYYY-MM-DD` with the original retrieval date. Use a fresh cache for a
live refresh. Review supplements separately; their dates never advance automatically.
Merged records retain the oldest applicable review date. Removing closed units or
changing aliases already present in the database requires separate review.

The catalog reviewed on 2026-10-04 contains 169 entities: 28 central matches and 152 regional
candidates, minus 13 BIP URL overlaps and two reviewed aliases, plus four additions.
The central export contains 13,367 subjects; its SHA-256 and collection counts are
stored in the snapshot. Every entity retains its source URLs and verification date.

Known gaps:

- Selection by name is incomplete. Five municipal guards were found: Kraków, Tarnów,
  Bochnia, Wieliczka and Skawina.
- All 169 entries have a complete numbered address. 165 have a published email;
  the three active entries without a general mailbox have a published telephone
  or contact form. Trzebinia's company in liquidation keeps its historical entry
  with `is_active=false` and is excluded from recommendations.
- `teryt_code` still describes a related locality, not a service boundary.
  `seat_teryt` comes from the municipality boundary containing the geocoded seat.
- Every active entry has a usable contact URI. Descriptions distinguish general
  correspondence from dedicated intervention or emergency channels.
- Central XML publication dates are empty. Reading an official source does not
  guarantee its contacts are current; reviewed supplements correct known differences.

Normal startup also imports `db/seeds/service_entity_seats.json`. This frozen
snapshot covers all 169 addresses and stores precise points, municipality codes,
review dates, sources and notes. No live geocoding runs during startup. The import
rejects stale address snapshots and preserves IDs and unchanged seat timestamps.
Unresolved entries can retain an independently verified live seat, but a changed
address cannot use old coordinates in recommendations.

162 seats use exact PRG address points. Four use the exact pins of maps linked or
embedded on institutional contact pages (Szczawnica, Osiek, Kęty and the Dąbrowa
Tarnowska road manager). Three use a secondary Google Maps address pin with the
full official address label: Bolesław Osadowa 1, Szczurowa Rynek 3C and Bobowa
Bohaterów Bobowej 6A. Their notes explicitly distinguish these from coordinates
published by the institution. Locality centers, street centers and neighboring
house numbers are never used. Review these seven exceptions when refreshing.

To collect a new seat snapshot, run from `apps/api` with the configured database
available for read-only PostGIS coordinate conversion:

```sh
uv run --env-file ../../.env python -m app.collect_service_entity_seats --catalog ../../db/seeds/service_entities.json --reviews ../../db/seeds/service_entity_seat_reviews.json --output ../../db/seeds/service_entity_seats.json
```

Review `service_entity_seat_reviews.json` against its linked sources before this
command. Reviewed street aliases preserve the published address, and office units
are resolved to their verified building. Any address change invalidates its review.
The collector resolves every point's actual municipality through ULDK. Network
errors abort without replacing the file. Compare the generated diff before import.

Test fixtures are small extracts of official BIP XML and regional API articles.
They cover filtering, contact parsing and role separation; they are not seed data.
