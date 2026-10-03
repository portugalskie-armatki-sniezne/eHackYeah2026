# Database startup and validation

From the repository root, run:

```sh
docker compose up
```

Compose discovers the root `docker-compose.yaml`. It provides local defaults; `.env` is optional.
The seed image uses `tooling/seed/Dockerfile` and `tooling/seed/requirements.txt`.
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
distance queries, report grouping, photo relationships, edit timestamps, and migration
rollback/reapply. Its containers, volume, and local image tag are removed afterward.

Report locations use `geography(Point, 4326)`. Supply longitude before latitude, for
example `ST_SetSRID(ST_MakePoint(19.94, 50.06), 4326)::geography`. Validate longitude
within -180 to 180 and latitude within -90 to 90 in the API before inserting; PostGIS
geography can normalize out-of-range inputs. `ST_DWithin` uses meters with this type.
The institution workbook contains addresses, but no coordinates or boundary polygons.

Each report can belong to one optional group with a shared response. Each photo row
contains a persistent storage key; the API/storage layer owns file upload, access,
and deletion. Deleting a report removes its photo rows, while deleting a group
ungroups its reports. `edited_at` is maintained by database triggers. The API must
store a complete encoded password hash (including its salt) in `users.password_hash`.
