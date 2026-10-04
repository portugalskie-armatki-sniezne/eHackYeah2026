"""import both official institution datasets in one transaction."""

import argparse
from pathlib import Path
import sys

import psycopg
import xlrd

from import_local_government_offices import import_contacts, read_contacts
from import_service_entities import import_entities, read_entities
from import_service_entity_seats import import_seats, read_seats


def import_data(connection: psycopg.Connection, offices: list[tuple], entities: list[dict], seats=None) -> tuple[int, int]:
    with connection.transaction():
        counts = import_contacts(connection, offices), import_entities(connection, entities)
        if seats is not None:
            import_seats(connection, seats, entities)
        return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("entities", type=Path)
    args = parser.parse_args()
    try:
        offices = read_contacts(args.workbook)
        entities = read_entities(args.entities)
        seats = read_seats(args.entities.with_name("service_entity_seats.json"), entities)
        with psycopg.connect(connect_timeout=10) as connection:
            office_changes, entity_changes = import_data(connection, offices, entities, seats)
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
