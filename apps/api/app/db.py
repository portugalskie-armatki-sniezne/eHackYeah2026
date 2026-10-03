import os
from collections.abc import Iterator

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def conninfo() -> str:
    # defaults match docker-compose.yaml, values come from the root .env.
    return make_conninfo(
        host="127.0.0.1",
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "app_db"),
        user=os.environ.get("POSTGRES_USER", "app_user"),
        password=os.environ.get("POSTGRES_PASSWORD", "local_dev_password"),
    )


pool = ConnectionPool(
    conninfo(),
    open=False,
    kwargs={"autocommit": True, "row_factory": dict_row},
)


def get_connection() -> Iterator[psycopg.Connection]:
    with pool.connection() as connection:
        yield connection
