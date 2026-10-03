# Database startup and validation

From the repository root, run:

```sh
task db
```

The command starts Compose services from the root `docker-compose.yaml` and waits for seed import to finish. PostgreSQL stays running afterward. Compose provides local defaults; `.env` is optional.
The seed image uses `tooling/seed/Dockerfile`, `tooling/seed/pyproject.toml`, and `tooling/seed/uv.lock`.
To inspect migration and import output, run `docker compose logs db-migrator db-seeder`.

Startup waits for PostgreSQL, applies dbmate migrations, then imports
`db/seeds/teleaddr_base_16042026.xls`. The importer requires the source's 22 headers,
normalizes numeric cells and blank values, and upserts contacts by their seven-digit
TERYT code in one transaction. Repeated runs preserve IDs and unchanged rows. Source
updates replace the corresponding contact fields; contacts absent from the workbook
are retained. Polish source values are preserved; database identifiers are English.

The PostGIS image keeps PostgreSQL 18 and the `/var/lib/postgresql` volume path.
The upstream image supports amd64, so ARM machines need Docker's amd64 emulation.
These edited initial migrations target a fresh database. If version 01 was already
applied, dbmate will not replay it; preserve existing data with a forward migration
before using the new schema. Do not delete an existing volume to apply these edits.

Run the database checks with Docker running:

```sh
python3 tests/check_database.py
```

This builds the importer and creates a uniquely named Compose project with test
credentials and a separate database volume. It checks startup ordering, all 203 source
records, repeat startup, XLS conversion and validation, atomic upserts, spatial
distance queries, reports saved before classification, master report links and independent
content, statuses, responsible institutions, shared comments and likes, photo relationships,
edit timestamps, and reference data rollback. All four migrations are rolled back and
reapplied. Its containers, volume, and local image tag are removed afterward.

Report locations use `geography(Point, 4326)`. Supply longitude before latitude, for
example `ST_SetSRID(ST_MakePoint(19.94, 50.06), 4326)::geography`. Validate longitude
within -180 to 180 and latitude within -90 to 90 in the API before inserting; PostGIS
geography can normalize out-of-range inputs. `ST_DWithin` uses meters with this type.
The institution workbook contains addresses, but no coordinates or boundary polygons.

Reports are saved before classification, with no master assigned. The backend then
creates a master from the first report or links the report to an existing master.
Master content is independent of individual reports; statuses and responsible institutions
belong to masters. Comments and likes also belong to masters. Categories and statuses
are populated by migration 04. Each photo row contains a persistent storage key;
the API/storage layer owns file upload, access,
and deletion. Deleting a report removes its photo rows and preserves its master and
the shared discussion. A master with linked reports cannot be deleted.
`users.edited_at`, `reports.edited_at`, and `master_reports.edited_at` are maintained
by database triggers. Users must provide at least one nonblank email or phone number;
email and phone are unique. `users.role` is `user`, `office`, or `admin` and defaults
to `user`. The API must store a complete encoded password hash (including its salt)
in `users.password_hash`.

Migrations 01 and 02 create the tables, migration 03 adds constraints, and migration
04 inserts the initial categories (`improvement`, `issue`) and master report statuses.
The statuses mean: `created` is saved in the application, `reported` is successfully
sent to the responsible institution, `inprogress` has confirmed work in progress,
and `finished` has confirmed completion. The backend owns classification, master
creation and assignment, and status transitions.
