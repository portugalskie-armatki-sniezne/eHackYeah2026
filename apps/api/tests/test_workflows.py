import base64
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from psycopg import sql
from psycopg.rows import dict_row

from app import storage, visualizations
from app import workflow_worker as worker
from app.db import conninfo
from app.models import User
from app.workflow_settings import settings
from conftest import PNG, create_report, random_location, reference_id


@pytest.fixture(autouse=True)
def workflow_configuration(monkeypatch):
    monkeypatch.setenv("GEMINI_USER_LIMIT", "10")
    monkeypatch.setenv("SMTP_USER_LIMIT", "50")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "86400")
    monkeypatch.setenv("VISUALIZATION_DRAFT_TTL_DAYS", "7")
    monkeypatch.setenv("SMTP_MOCK", "true")
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", "demo@example.com")


def generate(client, headers, *, key=None, draft_id=None, description="A playground"):
    data = {"description": description}
    if draft_id:
        data["draft_id"] = str(draft_id)
    return client.post(
        "/visualizations",
        headers=headers | {"Idempotency-Key": key or str(uuid4())},
        data=data,
        files={"photos": ("site.png", PNG, "image/png")},
    )


def image_response(data=PNG):
    return {
        "prompt": "A playground in the same location",
        "media_type": "image/png",
        "image_base64": base64.b64encode(data).decode(),
    }


def process(connection, monkeypatch, kind="visualization", response=None):
    job = worker.claim(connection, kind, settings())
    assert job is not None
    monkeypatch.setattr(worker, "post_json", lambda *args: response or image_response())
    worker.execute(connection, kind, job, settings())
    return job


def test_draft_is_private_and_publication_preserves_history(client, signed_in, connection, monkeypatch):
    _, headers = signed_in()
    _, other = signed_in()
    first = generate(client, headers).json()
    assert first["status"] == "queued" and first["url"] is None
    assert first["status_url"] == f"/visualizations/{first['id']}"
    process(connection, monkeypatch)
    ready = client.get(first["status_url"], headers=headers).json()
    assert ready["generated"] and client.get(ready["url"]).status_code == 401
    assert client.get(ready["url"], headers=other).status_code == 403
    assert client.get(ready["url"], headers=headers).content == PNG
    second = generate(client, headers, draft_id=first["draft_id"]).json()
    process(connection, monkeypatch, response=image_response(PNG + b"second"))
    report = create_report(
        client, headers, random_location(), category="improvement", visualization_draft_id=first["draft_id"]
    )
    assert len(report["photos"]) == 1
    history = client.get(f"/reports/{report['id']}/visualizations").json()
    assert history["total"] == 2
    assert history["items"][0]["id"] == second["id"]
    assert client.get(ready["url"]).content == PNG
    assert client.get(f"/master-reports/{report['master_report_id']}/visualizations").json()["total"] == 2


def test_idempotency_and_one_active_generation(client, signed_in, connection):
    user, headers = signed_in()
    key = str(uuid4())
    first = generate(client, headers, key=key)
    assert first.status_code == 202
    assert generate(client, headers, key=key).json()["id"] == first.json()["id"]
    assert generate(client, headers, key=key, description="Different design").status_code == 409
    assert generate(client, headers).status_code == 409
    assert (
        connection.execute("SELECT count(*) AS n FROM visualization_jobs WHERE user_id = %s", (user["id"],)).fetchone()[
            "n"
        ]
        == 1
    )


def test_failed_attempts_share_limit_across_drafts_and_reports(client, signed_in, connection, monkeypatch):
    user, headers = signed_in()
    report = create_report(client, headers, random_location(), category="improvement", photos=[PNG])
    for index in range(10):
        if index % 2:
            response = client.post(
                f"/reports/{report['id']}/visualizations", headers=headers | {"Idempotency-Key": str(uuid4())}
            )
        else:
            response = generate(client, headers)
        assert response.status_code == 202
        process(connection, monkeypatch, response={"image_base64": "invalid"})
    rejected = generate(client, headers)
    assert rejected.status_code == 429 and int(rejected.headers["Retry-After"]) > 0
    client.delete(f"/reports/{report['id']}", headers=headers)
    worker.cleanup(connection)
    assert generate(client, headers).status_code == 429
    assert (
        connection.execute("SELECT count(*) AS n FROM visualization_jobs WHERE user_id = %s", (user["id"],)).fetchone()[
            "n"
        ]
        == 10
    )
    monkeypatch.setenv("GEMINI_USER_LIMIT", "11")
    assert generate(client, headers).status_code == 202


def test_failed_job_replay_requires_new_key_for_another_attempt(client, signed_in, connection, monkeypatch):
    _, headers = signed_in()
    first = generate(client, headers, key="first").json()
    process(connection, monkeypatch, response={"image_base64": "invalid"})
    replay = generate(client, headers, key="first").json()
    assert replay["id"] == first["id"] and replay["status"] == "failed"
    assert generate(client, headers, key="retry", draft_id=first["draft_id"]).status_code == 202


def test_missing_draft_source_rolls_back_publication(client, signed_in, connection):
    user, headers = signed_in()
    draft = generate(client, headers).json()
    keys = connection.execute("SELECT source_keys FROM visualization_jobs WHERE id = %s", (draft["id"],)).fetchone()[
        "source_keys"
    ]
    storage.delete(keys)
    form = {
        "report_category_id": reference_id(client, "/report-categories", "improvement"),
        "title": "A playground",
        "description": "A playground",
        **random_location(),
        "visualization_draft_id": draft["draft_id"],
    }
    assert client.post("/reports", data=form, headers=headers).status_code == 404
    for table in ("reports", "mail_delivery_jobs"):
        assert (
            connection.execute(f"SELECT count(*) AS n FROM {table} WHERE user_id = %s", (user["id"],)).fetchone()["n"]
            == 0
        )
    assert client.get(draft["status_url"], headers=headers).json()["report_id"] is None


def test_only_improvement_owner_can_generate_or_attach(client, signed_in, connection):
    _, headers = signed_in()
    _, other = signed_in()
    issue = create_report(client, headers, random_location(), photos=[PNG])
    endpoint = f"/reports/{issue['id']}/visualizations"
    assert client.post(endpoint, headers=headers | {"Idempotency-Key": "issue"}).status_code == 422
    initiative = create_report(client, headers, random_location(), category="improvement", photos=[PNG])
    assert (
        client.post(
            f"/reports/{initiative['id']}/visualizations", headers=other | {"Idempotency-Key": "foreign"}
        ).status_code
        == 403
    )
    draft = generate(client, headers).json()
    form = {
        "report_category_id": reference_id(client, "/report-categories", "improvement"),
        "title": "A new playground",
        "description": "A playground",
        **random_location(),
        "visualization_draft_id": draft["draft_id"],
    }
    assert client.post("/reports", data=form, headers=other).status_code == 403


@pytest.mark.parametrize("successful", [True, False])
def test_mail_waits_for_generation_then_reports_success(client, signed_in, connection, monkeypatch, successful):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    _, headers = signed_in()
    draft = generate(client, headers).json()
    report = create_report(
        client, headers, random_location(), category="improvement", visualization_draft_id=draft["draft_id"]
    )
    master = report["master_report_id"]
    assert worker.claim(connection, "mail", settings()) is None
    process(connection, monkeypatch, response=image_response() if successful else {"image_base64": "bad"})
    mail = worker.claim(connection, "mail", settings())
    assert mail is not None
    calls = []

    def send(url, payload, timeout):
        calls.append(payload)
        return {"status": "sent"}

    monkeypatch.setattr(worker, "post_json", send)
    worker.execute(connection, "mail", mail, settings())
    assert calls[0]["to"] == "demo@example.com"
    assert len(calls[0]["photos"]) == (2 if successful else 1)
    assert client.get(f"/master-reports/{master}").json()["status_id"] == reference_id(
        client, "/master-report-statuses", "reported"
    )
    assert client.get(f"/master-reports/{master}/delivery", headers=headers).json()["status"] == "sent"
    assert worker.claim(connection, "mail", settings()) is None
    client.post(f"/reports/{report['id']}/visualizations", headers=headers | {"Idempotency-Key": "later"})
    assert worker.claim(connection, "mail", settings()) is None


def test_joining_existing_master_does_not_queue_mail(client, signed_in, connection):
    _, headers = signed_in()
    _, other = signed_in()
    location = random_location()
    first = create_report(client, headers, location)
    second = create_report(client, other, location)
    assert first["master_report_id"] == second["master_report_id"]
    assert (
        connection.execute(
            "SELECT count(*) AS n FROM mail_delivery_jobs WHERE master_report_id = %s", (first["master_report_id"],)
        ).fetchone()["n"]
        == 1
    )


@pytest.mark.parametrize("destination,flag", [("demo@example.com", "false"), ("invalid", "true"), ("", "true")])
def test_api_blocks_unsafe_smtp_configuration(client, signed_in, connection, monkeypatch, destination, flag):
    _, headers = signed_in()
    report = create_report(client, headers, random_location())
    monkeypatch.setenv("SMTP_MOCK", flag)
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", destination)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    assert worker.claim(connection, "mail", settings()) is None
    delivery = client.get(f"/master-reports/{report['master_report_id']}/delivery", headers=headers).json()
    assert delivery["status"] == "queued" and delivery["error_code"] == "smtp_configuration"
    assert delivery["dispatched_at"] is None
    assert client.get(f"/master-reports/{report['master_report_id']}").json()["status_id"] == reference_id(
        client, "/master-report-statuses", "created"
    )


@pytest.mark.parametrize("used", [49, 50])
def test_smtp_limit_defers_mail_without_spending_another_attempt(client, signed_in, connection, monkeypatch, used):
    user, headers = signed_in()
    report = create_report(client, headers, random_location())
    connection.execute(
        "INSERT INTO mail_delivery_jobs (user_id, payload, status, dispatched_at) "
        "SELECT %s, '{}'::jsonb, 'failed', statement_timestamp() FROM generate_series(1, %s)",
        (user["id"], used),
    )
    if used == 49:
        process(connection, monkeypatch, "mail", {"status": "sent"})
        client.delete(f"/reports/{report['id']}", headers=headers)
        report = create_report(client, headers, random_location())
    assert worker.claim(connection, "mail", settings()) is None
    delivery = client.get(f"/master-reports/{report['master_report_id']}/delivery", headers=headers).json()
    assert delivery["error_code"] == "smtp_limit" and delivery["dispatched_at"] is None
    connection.execute(
        "UPDATE mail_delivery_jobs SET dispatched_at = statement_timestamp() - interval '25 hours', "
        "next_attempt_at = statement_timestamp() WHERE user_id = %s",
        (user["id"],),
    )
    assert worker.claim(connection, "mail", settings()) is not None


def test_rejected_smtp_does_not_change_status(client, signed_in, connection, monkeypatch):
    _, headers = signed_in()
    report = create_report(client, headers, random_location())
    job = worker.claim(connection, "mail", settings())

    def reject(*args):
        raise worker.ProviderError(503)

    monkeypatch.setattr(worker, "post_json", reject)
    worker.execute(connection, "mail", job, settings())
    assert (
        client.get(f"/master-reports/{report['master_report_id']}/delivery", headers=headers).json()["status"]
        == "failed"
    )
    assert client.get(f"/master-reports/{report['master_report_id']}").json()["status_id"] == reference_id(
        client, "/master-report-statuses", "created"
    )


def test_uncertain_mail_is_not_retried_and_does_not_change_status(client, signed_in, connection, monkeypatch):
    _, headers = signed_in()
    report = create_report(client, headers, random_location())
    job = worker.claim(connection, "mail", settings())

    def timeout(*args):
        raise worker.ProviderError()

    monkeypatch.setattr(worker, "post_json", timeout)
    worker.execute(connection, "mail", job, settings())
    assert worker.claim(connection, "mail", settings()) is None
    assert (
        client.get(f"/master-reports/{report['master_report_id']}/delivery", headers=headers).json()["status"]
        == "unknown"
    )
    assert client.get(f"/master-reports/{report['master_report_id']}").json()["status_id"] == reference_id(
        client, "/master-report-statuses", "created"
    )


def test_mail_success_does_not_downgrade_progress(client, signed_in, connection, monkeypatch):
    _, headers = signed_in()
    report = create_report(client, headers, random_location())
    advanced = reference_id(client, "/master-report-statuses", "inprogress")
    connection.execute("UPDATE master_reports SET status_id = %s WHERE id = %s", (advanced, report["master_report_id"]))
    process(connection, monkeypatch, "mail", {"status": "sent"})
    assert client.get(f"/master-reports/{report['master_report_id']}").json()["status_id"] == advanced


def test_restart_recovers_expired_leases_without_repeating_provider_calls(client, signed_in, connection):
    _, headers = signed_in()
    draft = generate(client, headers).json()
    generation = worker.claim(connection, "visualization", settings())
    report = create_report(
        client, headers, random_location(), category="improvement", visualization_draft_id=draft["draft_id"]
    )
    connection.execute("UPDATE visualization_jobs SET lease_expires_at = statement_timestamp() - interval '1 second'")
    assert worker.claim(connection, "visualization", settings()) is None
    worker.finish_visualization(connection, generation, image_response())
    assert client.get(draft["status_url"], headers=headers).json()["status"] == "failed"
    worker.claim(connection, "mail", settings())
    connection.execute("UPDATE mail_delivery_jobs SET lease_expires_at = statement_timestamp() - interval '1 second'")
    assert worker.claim(connection, "mail", settings()) is None
    assert (
        client.get(f"/master-reports/{report['master_report_id']}/delivery", headers=headers).json()["status"]
        == "unknown"
    )


def test_storage_failure_preserves_previous_result(client, signed_in, connection, monkeypatch):
    _, headers = signed_in()
    first = generate(client, headers).json()
    process(connection, monkeypatch)
    ready = client.get(first["status_url"], headers=headers).json()
    second = generate(client, headers, draft_id=first["draft_id"]).json()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(storage, "save", fail)
    process(connection, monkeypatch)
    assert client.get(second["status_url"], headers=headers).json()["status"] == "failed"
    assert client.get(ready["url"], headers=headers).content == PNG


def test_cleanup_expires_drafts_but_keeps_published_files_and_attempts(client, signed_in, connection, monkeypatch):
    user, headers = signed_in()
    first = generate(client, headers).json()
    process(connection, monkeypatch)
    published = create_report(
        client, headers, random_location(), category="improvement", visualization_draft_id=first["draft_id"]
    )
    second = generate(client, headers).json()
    process(connection, monkeypatch)
    private = client.get(second["status_url"], headers=headers).json()
    folder = storage.file_path(f"visualizations/{second['id']}")
    (folder / "interrupted-write").write_bytes(b"orphaned temporary file")
    connection.execute("UPDATE visualization_drafts SET expires_at = statement_timestamp() - interval '1 day'")
    worker.cleanup(connection)
    assert not folder.exists()
    assert client.get(private["url"], headers=headers).status_code == 410
    assert client.get(f"/reports/{published['id']}/visualizations").json()["total"] == 1
    assert (
        connection.execute("SELECT count(*) AS n FROM visualization_jobs WHERE user_id = %s", (user["id"],)).fetchone()[
            "n"
        ]
        == 2
    )


def test_deleting_published_report_removes_images_but_keeps_usage(client, signed_in, connection, monkeypatch):
    user, headers = signed_in()
    draft = generate(client, headers).json()
    process(connection, monkeypatch)
    report = create_report(
        client, headers, random_location(), category="improvement", visualization_draft_id=draft["draft_id"]
    )
    folder = storage.file_path(f"visualizations/{draft['id']}")
    assert folder.is_dir()
    assert client.delete(f"/reports/{report['id']}", headers=headers).status_code == 204
    worker.cleanup(connection)
    assert not folder.exists()
    assert client.get(f"/visualizations/{draft['id']}/file", headers=headers).status_code == 410
    assert (
        connection.execute("SELECT count(*) AS n FROM visualization_jobs WHERE user_id = %s", (user["id"],)).fetchone()[
            "n"
        ]
        == 1
    )


def test_concurrent_idempotency_and_worker_claims(connection, upload_dir):
    # separate committed connections exercise locks rather than the endpoint fixture's savepoints.
    schema = f"workflow_{uuid4().hex}"
    with psycopg.connect(conninfo(), autocommit=True, row_factory=dict_row) as setup:
        setup.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            for table in ("users", "visualization_drafts", "visualization_jobs"):
                setup.execute(
                    sql.SQL("CREATE TABLE {}.{} (LIKE public.{} INCLUDING ALL)").format(
                        sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)
                    )
                )
            setup.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            row = setup.execute(
                "INSERT INTO users (first_name, last_name, password_hash, email) "
                "VALUES ('Test', 'User', 'test', %s) RETURNING *, false AS google_linked",
                (f"workflow-{uuid4().hex}@example.com",),
            ).fetchone()
            user = User.model_validate(row)
            key = str(uuid4())

            def submit(_):
                with psycopg.connect(
                    conninfo(), autocommit=True, row_factory=dict_row, options=f"-c search_path={schema},public"
                ) as db:
                    return visualizations.enqueue(db, user, key, "A playground", [("png", PNG)]).id

            def take(_):
                with psycopg.connect(
                    conninfo(), autocommit=True, row_factory=dict_row, options=f"-c search_path={schema},public"
                ) as db:
                    return worker.claim(db, "visualization", settings())

            with ThreadPoolExecutor(max_workers=2) as executor:
                ids = list(executor.map(submit, range(2)))
                assert ids[0] == ids[1]
                jobs = list(executor.map(take, range(2)))
                assert sum(job is not None for job in jobs) == 1
            assert (
                setup.execute("SELECT count(*) AS n FROM visualization_jobs WHERE user_id = %s", (user.id,)).fetchone()[
                    "n"
                ]
                == 1
            )
            setup.execute("UPDATE visualization_jobs SET status = 'failed'")
            setup.execute(
                "INSERT INTO visualization_jobs (id, user_id, idempotency_key, request_hash, description, "
                "source_keys, status) SELECT gen_random_uuid(), %s, 'prior-' || n, 'hash', 'A playground', "
                "'[]'::jsonb, 'failed' FROM generate_series(1, 8) AS n",
                (user.id,),
            )

            def at_limit(index):
                with psycopg.connect(
                    conninfo(), autocommit=True, row_factory=dict_row, options=f"-c search_path={schema},public"
                ) as db:
                    try:
                        visualizations.enqueue(db, user, f"limit-{index}", "A playground", [("png", PNG)])
                        return 202
                    except HTTPException as error:
                        return error.status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(at_limit, range(2)))
            assert sorted(statuses) == [202, 409]
            setup.execute("UPDATE visualization_jobs SET status = 'failed' WHERE status = 'queued'")
            assert at_limit(2) == 429
            assert setup.execute("SELECT count(*) AS n FROM visualization_jobs").fetchone()["n"] == 10
        finally:
            setup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
