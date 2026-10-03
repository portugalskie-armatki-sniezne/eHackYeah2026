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
edit timestamps, and reference data rollback. All five migrations are rolled back and
reapplied. Its containers, volume, and local image tag are removed afterward.

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
The statuses mean: `created` is saved in the application, `reported` is successfully
sent to the responsible institution, `inprogress` has confirmed work in progress,
and `finished` has confirmed completion. The backend owns classification, master
creation and assignment, and status transitions.

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
workbook and service entity JSON without fetching external sources. Both imports
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

The 2026-10-03 snapshot contains 169 entities: 28 central matches and 152 regional
candidates, minus 13 BIP URL overlaps and two reviewed aliases, plus four additions.
The central export contains 13,367 subjects; its SHA-256 and collection counts are
stored in the snapshot. Every entity retains its source URLs and verification date.

Known gaps:

- Selection by name is incomplete. Five municipal guards were found: Kraków, Tarnów,
  Bochnia, Wieliczka and Skawina.
- 78 entities lack email, 99 lack phone numbers, and 64 lack both. Their BIP links
  remain available. Unknown or ambiguous values stay NULL.
- 136 entities lack confirmed TERYT, 72 lack locality/postal code, and 86 lack
  street/house number. TERYT describes a related locality, not a service boundary.
- Only 12 dedicated reporting channels were confirmed. General contact details do
  not establish an intervention channel or responsibility for infrastructure.
- Central XML publication dates are empty. Reading an official source does not
  guarantee its contacts are current; reviewed supplements correct known differences.

Test fixtures are small extracts of official BIP XML and regional API articles.
They cover filtering, contact parsing and role separation; they are not seed data.
