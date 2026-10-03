"""validate Compose startup and migrations using a disposable database volume."""

import json
import os
from pathlib import Path
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    project = "ehack-db-check-" + uuid.uuid4().hex[:8]
    environment = os.environ | {
        "COMPOSE_PROJECT_NAME": project,
        "POSTGRES_DB": "schema_check",
        "POSTGRES_USER": "schema_check",
        "POSTGRES_PASSWORD": "test_only_password",
        # exercise the configurable port as well as the default PostgreSQL setup.
        "POSTGRES_PORT": "5543",
    }
    command = ["docker", "compose"]

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
                     "FROM institution_contacts c;")

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
            if name != f"/{service}":
                raise RuntimeError(f"Expected container name {service}, found {name}")

    try:
        compose("config", "--quiet")
        print("Building and starting isolated Compose services...", flush=True)
        compose("up", "-d")
        seed_completed()
        if query("SELECT COUNT(*) FROM institution_contacts;") != "203":
            raise RuntimeError("The workbook import did not produce 203 contacts")
        print("PASS: startup ran migrations and imported 203 contacts", flush=True)
        before = snapshot()
        compose("up", "-d")
        seed_completed()
        if snapshot() != before:
            raise RuntimeError("Repeated Compose startup changed contact rows or IDs")
        print("PASS: repeated Compose startup preserved contact data and IDs", flush=True)
        print(compose("run", "--rm", "--no-deps", "-e", "PYTHONPATH=/app",
                      "-v", f"{ROOT / 'tests'}:/tests:ro", "--entrypoint", "python", "db-seeder",
                      "/tests/test_contact_import.py"), flush=True)
        print("PASS: XLS parsing, upsert, and transaction rollback checks", flush=True)
        query((ROOT / "tests/fixtures/check_reports.sql").read_text())
        print("PASS: report grouping, geography, photos, and edit timestamps", flush=True)
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        compose("run", "--rm", "--no-deps", "db-migrator", "down")
        remaining = query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' "
                          "AND table_name IN ('users', 'reports', 'report_groups', 'report_photos', "
                          "'institution_contacts');")
        if remaining != "0":
            raise RuntimeError("Migration rollback left application tables behind")
        compose("run", "--rm", "--no-deps", "db-migrator", "up")
        compose("run", "--rm", "--no-deps", "db-seeder")
        if query("SELECT COUNT(*) FROM institution_contacts;") != "203":
            raise RuntimeError("Import after migration rollback failed")
        print("PASS: both migrations rolled back and reapplied successfully", flush=True)
    except Exception:
        print(compose("logs", "--no-color", "--tail", "50", check=False), flush=True)
        raise
    finally:
        compose("down", "--volumes", "--remove-orphans", "--rmi", "local")


if __name__ == "__main__":
    main()
