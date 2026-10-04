"""validate Compose startup and migrations using a disposable database volume."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    entity_count = len(json.loads((ROOT / "db/seeds/service_entities.json").read_text())["entities"])
    project = "ehack-db-check-" + uuid.uuid4().hex[:8]
    environment = os.environ | {
        "COMPOSE_PROJECT_NAME": project,
        "POSTGRES_DB": "schema_check",
        "POSTGRES_USER": "schema_check",
        "POSTGRES_PASSWORD": "test_only_password",
        # exercise the configurable port as well as the default PostgreSQL setup.
        "POSTGRES_PORT": "5543",
    }
    temporary_directory = tempfile.TemporaryDirectory(prefix=project + "-")
    override_path = Path(temporary_directory.name) / "compose.yaml"
    override_path.write_text("services:\n" + "".join(
        f"  {service}:\n    container_name: {project}-{service}\n"
        for service in ("db", "db-migrator", "db-seeder")
    ))
    command = ["docker", "compose", "--project-name", project,
               "-f", str(ROOT / "docker-compose.yaml"), "-f", str(override_path)]

    def compose(*args, input=None, check=True):
        result = subprocess.run(command + list(args), cwd=ROOT, env=environment,
                                input=input, text=True, capture_output=True)
        if check and result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout.strip()

    def query(statement):
        return compose("exec", "-T", "db", "psql", "-U", "schema_check", "-d", "schema_check",
                       "-p", "5543", "-v", "ON_ERROR_STOP=1", "-At", input=statement)

    def snapshot():
        return query("SELECT md5(string_agg(row_to_json(c)::text, '' ORDER BY teryt_code)) "
                     "FROM local_government_offices c; "
                     "SELECT md5(string_agg(row_to_json(e)::text, '' ORDER BY source_key)) "
                     "FROM service_entities e;")

    def seed_completed():
        compose("wait", "db-seeder")
        output = compose("ps", "-a", "--format", "json")
        containers = (json.loads(output) if output.lstrip().startswith("[")
                      else [json.loads(line) for line in output.splitlines() if line.strip()])
        for service in ("db-migrator", "db-seeder"):
            if not any(c["Service"] == service and c["State"] == "exited"
                       and c["ExitCode"] == 0 for c in containers):
                raise RuntimeError(f"{service} did not complete successfully")
        for service in ("db", "db-migrator", "db-seeder"):
            container_id = compose("ps", "--all", "--quiet", service)
            if not container_id:
                raise RuntimeError(f"No container was created for {service}")
            name = subprocess.run(
                ["docker", "inspect", "--format", "{{.Name}}", container_id],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            if name != f"/{project}-{service}":
                raise RuntimeError(f"Expected container name {project}-{service}, found {name}")

    try:
        compose("config", "--quiet")
        print("Building and starting isolated Compose services...", flush=True)
        compose("up", "-d")
        seed_completed()
        if query("SELECT COUNT(*) FROM local_government_offices;") != "203":
            raise RuntimeError("The workbook import did not produce 203 contacts")
        if query("SELECT COUNT(*) FROM service_entities;") != str(entity_count):
            raise RuntimeError("The service entity snapshot import is incomplete")
        seats = json.loads((ROOT / "db/seeds/service_entity_seats.json").read_text())["seats"]
        located = sum(seat["location"] is not None for seat in seats)
        if query("SELECT COUNT(*) FROM service_entities WHERE seat_location IS NOT NULL;") != str(located):
            raise RuntimeError("The reviewed seat snapshot import is incomplete")
        if query("SELECT to_regclass('institution_contacts') IS NULL;") != "t":
            raise RuntimeError("The old institution table still exists")
        print(f"PASS: startup imported 203 offices and {entity_count} service entities", flush=True)
        before = snapshot()
        categories_before = query("SELECT id, name FROM report_categories ORDER BY id;")
        statuses_before = query("SELECT id, name FROM master_report_statuses ORDER BY id;")
        compose("up", "-d")
        seed_completed()
        if snapshot() != before:
            raise RuntimeError("Repeated Compose startup changed contact rows or IDs")
        if query("SELECT id, name FROM report_categories ORDER BY id;") != categories_before:
            raise RuntimeError("Repeated Compose startup changed report categories or IDs")
        if query("SELECT id, name FROM master_report_statuses ORDER BY id;") != statuses_before:
            raise RuntimeError("Repeated Compose startup changed master report statuses or IDs")
        print("PASS: repeated Compose startup preserved contact data and IDs", flush=True)
        print(compose("run", "--rm", "--no-deps", "-e", "PYTHONPATH=/app",
                      "-v", f"{ROOT / 'tests'}:/tests:ro", "--entrypoint", "python", "db-seeder",
                      "/tests/test_contact_import.py"), flush=True)
        print(compose("run", "--rm", "--no-deps", "-e", "PYTHONPATH=/app",
                      "-v", f"{ROOT / 'tests'}:/tests:ro", "--entrypoint", "python", "db-seeder",
                      "/tests/test_service_entity_import.py"), flush=True)
        print("PASS: XLS, BIP parsing, entity roles, upserts, and transaction rollback checks", flush=True)
        query((ROOT / "tests/fixtures/check_reports.sql").read_text())
        query((ROOT / "tests/fixtures/check_constraints.sql").read_text())
        print("PASS: master reports, statuses, institutions, comments, likes, and constraints", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT to_regclass('notifications') IS NULL "
                 "AND to_regclass('master_report_photo_proposals') IS NULL;") != "t":
            raise RuntimeError("Notification and photo proposal rollback left its tables behind")
        print("PASS: notifications and photo proposals migration rolled back successfully", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' "
                 "AND table_name = 'master_report_comments' AND column_name = 'highlighted';") != "0":
            raise RuntimeError("Comment highlight rollback left the column behind")
        print("PASS: comment highlight migration rolled back successfully", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT to_regclass('projects') IS NULL AND to_regclass('project_chunks') IS NULL;") != "t":
            raise RuntimeError("Innovation library rollback left its tables behind")
        print("PASS: innovation library migration rolled back successfully", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT to_regclass('report_visualization_attempts') IS NULL;") != "t":
            raise RuntimeError("Visualization attempts migration rollback left its table behind")
        print("PASS: visualization attempts migration rolled back successfully", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' "
                 "AND table_name = 'service_entities' AND column_name = 'is_active';") != "0":
            raise RuntimeError("Activity rollback left the catalog flag behind")
        print("PASS: institution activity migration rolled back successfully", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' "
                 "AND table_name = 'service_entities' AND column_name IN "
                 "('seat_location', 'seat_teryt', 'seat_geocoded_at', 'seat_address');") != "0":
            raise RuntimeError("Seat rollback left institution columns behind")
        print("PASS: institution seat migration rolled back successfully", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        if query("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' "
                 "AND table_name = 'reports' AND column_name IN "
                 "('municipality_teryt', 'municipality_name', 'county_teryt', 'county_name');") != "0":
            raise RuntimeError("Municipality rollback left report columns behind")
        print("PASS: report municipality migration rolled back successfully", flush=True)
        query("INSERT INTO users (first_name, last_name, email, google_sub) "
              "VALUES ('Rollback', 'Check', 'rollback-check@example.invalid', 'rollback-check');")
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        sign_in = query("SELECT (SELECT password_hash FROM users WHERE email = 'rollback-check@example.invalid'), "
                        "(SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' "
                        "AND table_name = 'users' AND column_name = 'google_sub'), "
                        "(SELECT is_nullable FROM information_schema.columns WHERE table_schema = 'public' "
                        "AND table_name = 'users' AND column_name = 'password_hash');")
        if sign_in != "!|0|NO":
            raise RuntimeError("Google sign-in rollback did not restore the required password hash")
        print("PASS: Google sign-in rollback kept accounts without a password", flush=True)
        query("INSERT INTO report_categories (name) VALUES ('rollback_check_category'); "
              "INSERT INTO master_report_statuses (name) VALUES ('rollback_check_status');")
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        reference_rows = query("SELECT "
                               "(SELECT COUNT(*) FROM report_categories WHERE name IN ('improvement', 'issue')), "
                               "(SELECT COUNT(*) FROM master_report_statuses "
                               "WHERE name IN ('created', 'reported', 'inprogress', 'finished')), "
                               "(SELECT COUNT(*) FROM report_categories WHERE name = 'rollback_check_category'), "
                               "(SELECT COUNT(*) FROM master_report_statuses WHERE name = 'rollback_check_status');")
        if reference_rows != "0|0|1|1":
            raise RuntimeError("Reference data rollback did not remove only the seeded rows")
        print("PASS: reference data rollback preserved unrelated categories and statuses", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        constraints = query("SELECT COUNT(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                            "JOIN pg_namespace n ON n.oid = t.relnamespace "
                            "WHERE n.nspname = 'public' AND c.contype IN ('f', 'u', 'c') "
                            "AND t.relname IN ('users', 'report_categories', 'master_report_statuses', "
                            "'master_reports', 'reports', 'report_photos', 'master_report_comments', "
                            "'master_report_comment_likes', 'local_government_offices', 'service_entities');")
        if constraints != "0":
            raise RuntimeError("Constraint migration rollback left constraints behind")
        for _ in range(2):
            compose("run", "--rm", "--no-deps", "db-migrator", "down")
        remaining = query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' "
                          "AND table_name IN ('users', 'report_categories', 'master_report_statuses', "
                          "'master_reports', 'reports', 'report_photos', 'master_report_comments', "
                          "'report_visualization_attempts', 'master_report_comment_likes', "
                          "'local_government_offices', 'service_entities', 'projects', 'project_chunks');")
        if remaining != "0":
            raise RuntimeError("Migration rollback left application tables behind")
        compose("run", "--rm", "--no-deps", "db-migrator", "up")
        compose("run", "--rm", "--no-deps", "db-seeder")
        if query("SELECT COUNT(*) FROM local_government_offices;") != "203":
            raise RuntimeError("Import after migration rollback failed")
        if query("SELECT COUNT(*) FROM service_entities;") != str(entity_count):
            raise RuntimeError("Service entity import after migration rollback failed")
        if query("SELECT COUNT(*) FROM projects;") == "0":
            raise RuntimeError("Innovation library import after migration rollback failed")
        query((ROOT / "tests/fixtures/check_reports.sql").read_text())
        query((ROOT / "tests/fixtures/check_constraints.sql").read_text())
        print("PASS: all twelve migrations rolled back and reapplied successfully", flush=True)
    except Exception:
        print(compose("logs", "--no-color", "--tail", "50", check=False), flush=True)
        raise
    finally:
        try:
            compose("down", "--volumes", "--remove-orphans", "--rmi", "local")
        finally:
            temporary_directory.cleanup()


if __name__ == "__main__":
    main()
