import os
from collections.abc import Iterator

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def conninfo() -> str:
    # defaults match docker-compose.yaml, values come from the root .env.
    return make_conninfo(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "app_db"),
        user=os.environ.get("POSTGRES_USER", "app_user"),
        password=os.environ.get("POSTGRES_PASSWORD", "local_dev_password"),
    )


pool = ConnectionPool(
    conninfo(),
    open=False,
    # a request keeps its connection until it ends, so the default of 4 runs out under a few slow requests.
    min_size=4,
    max_size=20,
    # a request that cannot get a connection fails with 503 instead of hanging.
    timeout=10,
    kwargs={"autocommit": True, "row_factory": dict_row},
)


def get_connection() -> Iterator[psycopg.Connection]:
    with pool.connection() as connection:
        yield connection
