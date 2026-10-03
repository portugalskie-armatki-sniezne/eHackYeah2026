"""set the role of an existing user, for example to create the first admin."""

import argparse
import sys
from typing import get_args

import psycopg

from app.db import conninfo
from app.models import Role


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("role", choices=get_args(Role))
    args = parser.parse_args()

    try:
        with psycopg.connect(conninfo(), connect_timeout=10, autocommit=True) as connection:
            updated = connection.execute(
                "UPDATE users SET role = %s WHERE email = %s", (args.role, args.email)
            ).rowcount
    except psycopg.Error as error:
        # connection error messages can contain credentials or connection details.
        print(f"Setting role failed: database error ({error.sqlstate or 'connection failure'})", file=sys.stderr)
        return 1
    if not updated:
        print(f"No user with email {args.email}", file=sys.stderr)
        return 1
    print(f"{args.email} now has role {args.role}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
