"""import both official institution datasets in one transaction."""

import argparse
from pathlib import Path
import sys

import psycopg
import xlrd

from import_local_government_offices import import_contacts, read_contacts
from import_service_entities import import_entities, read_entities


def import_data(connection: psycopg.Connection, offices: list[tuple], entities: list[dict]) -> tuple[int, int]:
    with connection.transaction():
        return import_contacts(connection, offices), import_entities(connection, entities)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("entities", type=Path)
    args = parser.parse_args()
    try:
        offices = read_contacts(args.workbook)
        entities = read_entities(args.entities)
        with psycopg.connect(connect_timeout=10) as connection:
            office_changes, entity_changes = import_data(connection, offices, entities)
    except (OSError, ValueError, KeyError, xlrd.XLRDError) as error:
        print(f"Reference import failed: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"Reference import failed: database error ({error.sqlstate or 'connection failure'})",
              file=sys.stderr)
        return 1
    print(f"Imported {len(offices)} local government offices ({office_changes} inserted or updated).")
    print(f"Imported {len(entities)} service entities ({entity_changes} inserted or updated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
