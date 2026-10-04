import asyncio
import base64
import binascii
import json
import logging
import shutil
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg

from app import storage
from app.workflow_settings import Settings, settings, smtp_destination

logger = logging.getLogger(__name__)
TABLES = {"visualization": "visualization_jobs", "mail": "mail_delivery_jobs"}
LOCKS = {"visualization": 20260002, "mail": 20260003}
LEASE_SECONDS = 60


class ProviderError(Exception):
    def __init__(self, status_code: int | None = None):
        self.status_code = status_code


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ProviderError()
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ProviderError()
        return result
    except HTTPError as error:
        raise ProviderError(error.code) from None
    except (URLError, OSError, ValueError):
        raise ProviderError() from None


def recover(connection: psycopg.Connection, kind: str) -> None:
    table = TABLES[kind]
    outcome = "failed" if kind == "visualization" else "unknown"
    connection.execute(
        f"UPDATE {table} SET status = %s, error_code = 'interrupted', completed_at = statement_timestamp(), "
        "lease_token = NULL, lease_expires_at = NULL WHERE status = 'running' "
        "AND lease_expires_at <= statement_timestamp()",
        (outcome,),
    )


def claim(connection: psycopg.Connection, kind: str, config: Settings) -> dict | None:
    table = TABLES[kind]
    with connection.transaction():
        locked = connection.execute("SELECT pg_try_advisory_xact_lock(%s) AS locked", (LOCKS[kind],)).fetchone()[
            "locked"
        ]
        if not locked:
            return None
        recover(connection, kind)
        if connection.execute(f"SELECT id FROM {table} WHERE status = 'running' LIMIT 1").fetchone():
            return None
        if kind == "visualization":
            job = connection.execute(
                "SELECT j.* FROM visualization_jobs j JOIN visualization_drafts d ON d.id = j.draft_id "
                "WHERE j.status = 'queued' AND (d.report_id IS NOT NULL OR (d.published_at IS NULL "
                "AND d.expires_at > statement_timestamp())) ORDER BY j.created_at, j.id "
                "FOR UPDATE OF j SKIP LOCKED LIMIT 1"
            ).fetchone()
        else:
            job = connection.execute(
                "SELECT j.* FROM mail_delivery_jobs j LEFT JOIN visualization_jobs v ON v.id = j.visualization_job_id "
                "WHERE j.status = 'queued' AND j.next_attempt_at <= statement_timestamp() "
                "AND (v.id IS NULL OR v.status NOT IN ('queued', 'running')) "
                "ORDER BY j.next_attempt_at, j.created_at, j.id FOR UPDATE OF j SKIP LOCKED LIMIT 1"
            ).fetchone()
        if job is None:
            return None
        if kind == "mail":
            if job["master_report_id"] is None:
                connection.execute(
                    "UPDATE mail_delivery_jobs SET status = 'failed', error_code = 'report_deleted', "
                    "completed_at = statement_timestamp() WHERE id = %s",
                    (job["id"],),
                )
                return None
            try:
                job["destination"] = smtp_destination()
            except ValueError:
                connection.execute(
                    "UPDATE mail_delivery_jobs SET error_code = 'smtp_configuration', "
                    "next_attempt_at = statement_timestamp() + interval '60 seconds' WHERE id = %s",
                    (job["id"],),
                )
                return None
            user = connection.execute(
                "SELECT id FROM users WHERE id = %s FOR NO KEY UPDATE SKIP LOCKED", (job["user_id"],)
            ).fetchone()
            if user is None:
                return None
            usage = connection.execute(
                "SELECT count(*) AS count, min(dispatched_at) + %s * interval '1 second' AS next_at "
                "FROM mail_delivery_jobs WHERE user_id = %s "
                "AND dispatched_at > statement_timestamp() - %s * interval '1 second'",
                (config.window_seconds, job["user_id"], config.window_seconds),
            ).fetchone()
            if usage["count"] >= config.smtp_user_limit:
                connection.execute(
                    "UPDATE mail_delivery_jobs SET next_attempt_at = %s, error_code = 'smtp_limit' WHERE id = %s",
                    (usage["next_at"], job["id"]),
                )
                return None
            generation = connection.execute(
                "SELECT storage_key FROM visualization_jobs WHERE id = %s AND status = 'succeeded'",
                (job["visualization_job_id"],),
            ).fetchone()
            job["generated_key"] = generation["storage_key"] if generation else None
        token = uuid4()
        dispatched = ", dispatched_at = statement_timestamp()" if kind == "mail" else ""
        connection.execute(
            f"UPDATE {table} SET status = 'running', error_code = NULL, lease_token = %s, "
            f"lease_expires_at = statement_timestamp() + %s * interval '1 second'{dispatched} WHERE id = %s",
            (token, LEASE_SECONDS, job["id"]),
        )
        return job | {"lease_token": token}


def finish_error(connection: psycopg.Connection, kind: str, job: dict, outcome: str, code: str) -> None:
    connection.execute(
        f"UPDATE {TABLES[kind]} SET status = %s, error_code = %s, completed_at = statement_timestamp(), "
        "lease_token = NULL, lease_expires_at = NULL WHERE id = %s AND status = 'running' AND lease_token = %s",
        (outcome, code, job["id"], job["lease_token"]),
    )


def finish_visualization(connection: psycopg.Connection, job: dict, response: dict) -> None:
    try:
        data = base64.b64decode(response["image_base64"], validate=True)
        extension = storage.detect_extension(data)
        media_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(extension)
        prompt = response["prompt"]
        if not data or len(data) > storage.MAX_PHOTO_BYTES or media_type != response.get("media_type"):
            raise ValueError()
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError()
    except (KeyError, ValueError, TypeError, binascii.Error):
        finish_error(connection, "visualization", job, "failed", "invalid_image")
        return
    with storage.cleanup_on_error() as saved, connection.transaction():
        draft = connection.execute(
            "SELECT id FROM visualization_drafts WHERE id = %s AND (report_id IS NOT NULL OR "
            "(published_at IS NULL AND expires_at > statement_timestamp())) FOR UPDATE",
            (job["draft_id"],),
        ).fetchone()
        active = connection.execute(
            "SELECT id FROM visualization_jobs WHERE id = %s AND status = 'running' AND lease_token = %s "
            "AND lease_expires_at > statement_timestamp() FOR UPDATE",
            (job["id"], job["lease_token"]),
        ).fetchone()
        if not draft or not active:
            finish_error(connection, "visualization", job, "failed", "resource_expired")
            return
        key = f"visualizations/{job['id']}/result.{extension}"
        saved.append(key)
        storage.save(key, data)
        connection.execute(
            "UPDATE visualization_jobs SET status = 'succeeded', storage_key = %s, media_type = %s, prompt = %s, "
            "completed_at = statement_timestamp(), lease_token = NULL, lease_expires_at = NULL WHERE id = %s",
            (key, media_type, prompt, job["id"]),
        )


def finish_mail(connection: psycopg.Connection, job: dict) -> None:
    with connection.transaction():
        # lock the master before the delivery, matching publication and deletion lock order.
        master = connection.execute(
            "SELECT id FROM master_reports WHERE id = %s FOR UPDATE", (job["master_report_id"],)
        ).fetchone()
        accepted = connection.execute(
            "UPDATE mail_delivery_jobs SET status = 'sent', completed_at = statement_timestamp(), "
            "lease_token = NULL, lease_expires_at = NULL WHERE id = %s AND status = 'running' "
            "AND lease_token = %s AND lease_expires_at > statement_timestamp() RETURNING id",
            (job["id"], job["lease_token"]),
        ).fetchone()
        if accepted and master:
            connection.execute(
                "UPDATE master_reports SET status_id = (SELECT id FROM master_report_statuses WHERE name = 'reported') "
                "WHERE id = %s AND status_id = (SELECT id FROM master_report_statuses WHERE name = 'created')",
                (job["master_report_id"],),
            )


def execute(connection: psycopg.Connection, kind: str, job: dict, config: Settings) -> None:
    try:
        if kind == "visualization":
            response = post_json(
                config.gemini_url + "/generate",
                {
                    "report_type": "improvement",
                    "description": job["description"],
                    "photos": [{"storage_key": key} for key in job["source_keys"]],
                },
                300,
            )
            finish_visualization(connection, job, response)
        else:
            payload = job["payload"] | {"to": job["destination"]}
            if job["generated_key"]:
                payload["photos"] = [*payload["photos"], {"storage_key": job["generated_key"]}]
            response = post_json(config.notify_url + "/send", payload, 60)
            if response.get("status") != "sent":
                raise ProviderError()
            finish_mail(connection, job)
    except ProviderError as error:
        outcome = "unknown" if kind == "mail" and error.status_code in (None, 502, 504) else "failed"
        finish_error(connection, kind, job, outcome, "provider_error")
    except Exception:
        # never log provider payloads, recipients, credentials, or generated content.
        logger.warning("Workflow execution failed: %s", kind)
        finish_error(connection, kind, job, "unknown" if kind == "mail" else "failed", "execution_error")


def cleanup(connection: psycopg.Connection) -> None:
    with connection.transaction():
        drafts = connection.execute(
            "SELECT id FROM visualization_drafts WHERE (published_at IS NULL AND expires_at <= statement_timestamp()) "
            "OR (published_at IS NOT NULL AND report_id IS NULL) FOR UPDATE SKIP LOCKED"
        ).fetchall()
        for draft in drafts:
            jobs = connection.execute(
                "SELECT id FROM visualization_jobs WHERE draft_id = %s", (draft["id"],)
            ).fetchall()
            for job in jobs:
                try:
                    shutil.rmtree(storage.file_path(f"visualizations/{job['id']}"))
                except FileNotFoundError:
                    pass
            connection.execute(
                "UPDATE visualization_jobs SET status = 'failed', error_code = 'resource_expired', source_keys = '[]', "
                "storage_key = NULL, lease_token = NULL, lease_expires_at = NULL, "
                "completed_at = COALESCE(completed_at, statement_timestamp()) WHERE draft_id = %s",
                (draft["id"],),
            )
            connection.execute("DELETE FROM visualization_drafts WHERE id = %s", (draft["id"],))


def with_connection(pool, function, *args):
    with pool.connection() as connection:
        return function(connection, *args)


def renew(connection: psycopg.Connection, kind: str, job: dict) -> None:
    connection.execute(
        f"UPDATE {TABLES[kind]} SET lease_expires_at = statement_timestamp() + %s * interval '1 second' "
        "WHERE id = %s AND status = 'running' AND lease_token = %s AND lease_expires_at > statement_timestamp()",
        (LEASE_SECONDS, job["id"], job["lease_token"]),
    )


async def heartbeat(pool, kind: str, job: dict) -> None:
    while True:
        await asyncio.sleep(10)
        await asyncio.to_thread(with_connection, pool, renew, kind, job)


async def run(pool, kind: str) -> None:
    while True:
        beat = None
        try:
            if kind == "visualization":
                await asyncio.to_thread(with_connection, pool, cleanup)
            config = settings()
            job = await asyncio.to_thread(with_connection, pool, claim, kind, config)
            if job:
                beat = asyncio.create_task(heartbeat(pool, kind, job))
                await asyncio.to_thread(with_connection, pool, execute, kind, job, config)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Workflow worker unavailable: %s", kind)
        finally:
            if beat is not None:
                beat.cancel()
                await asyncio.gather(beat, return_exceptions=True)
        await asyncio.sleep(1)


def start(pool) -> list[asyncio.Task]:
    return [asyncio.create_task(run(pool, kind)) for kind in TABLES]


async def stop(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
