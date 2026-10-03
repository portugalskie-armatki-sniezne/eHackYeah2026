"""import the institution contact workbook without duplicating TERYT codes."""

import argparse
import math
from pathlib import Path
import re
import sys

import psycopg
from psycopg import sql
import xlrd


SOURCE_COLUMNS = {
    "Kod_TERYT": "teryt_code",
    "nazwa_samorządu": "local_government_name",
    "Województwo": "province",
    "Powiat": "county",
    "typ_JST": "local_government_type",
    "nazwa_urzędu_JST": "office_name",
    "miejscowość": "locality",
    "Kod pocztowy": "postal_code",
    "poczta": "post_office",
    "Ulica": "street",
    "Nr domu": "house_number",
    "telefon kierunkowy": "phone_area_code",
    "telefon": "phone_number",
    "telefon 2": "alternate_phone_number",
    "wewnętrzny": "phone_extension",
    "FAX kierunkowy": "fax_area_code",
    "FAX": "fax_number",
    "FAX wewnętrzny": "fax_extension",
    "ogólny adres poczty elektronicznej gminy/powiatu/województwa": "email",
    "adres www jednostki": "website",
    "ESP": "electronic_inbox",
    "adres doręczeń elektronicznych ADE": "electronic_delivery_address",
}


def normalize_header(value: str) -> str:
    return " ".join(value.split()).casefold()


def cell_text(cell: xlrd.sheet.Cell) -> str | None:
    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if cell.ctype == xlrd.XL_CELL_NUMBER and math.isfinite(cell.value):
        return str(int(cell.value)) if cell.value.is_integer() else str(cell.value)
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return cell.value.strip() or None
    raise ValueError("Expected text or a finite number in a contact cell")


def read_contacts(path: Path) -> list[tuple[str | None, ...]]:
    with xlrd.open_workbook(path, on_demand=True) as workbook:
        if workbook.nsheets != 1:
            raise ValueError("Expected exactly one contact worksheet")
        sheet = workbook.sheet_by_index(0)
        if sheet.nrows < 2:
            raise ValueError("The contact worksheet has no data rows")
        headers = [normalize_header(str(value)) for value in sheet.row_values(0)]
        expected = [normalize_header(header) for header in SOURCE_COLUMNS]
        if len(headers) != len(expected) or set(headers) != set(expected):
            raise ValueError("The contact worksheet headers do not match the expected 22 columns")
        positions = [headers.index(header) for header in expected]
        rows = []
        seen_codes = set()
        for row_number in range(1, sheet.nrows):
            try:
                cells = [sheet.cell(row_number, position) for position in positions]
                values = [cell_text(cell) for cell in cells]
                if not any(value is not None for value in values):
                    continue
                code = values[0]
                if code is None or not re.fullmatch(r"[0-9]{1,7}", code):
                    raise ValueError("Invalid TERYT code")
                # numeric Excel cells can lose the initial zero in a code.
                values[0] = code.zfill(7)
                if values[0] in seen_codes:
                    raise ValueError("Duplicate TERYT code")
                if values[1] is None:
                    raise ValueError("Missing local government name")
                if cells[7].ctype == xlrd.XL_CELL_NUMBER:
                    postal_code = values[7].zfill(5)
                    if not re.fullmatch(r"[0-9]{5}", postal_code):
                        raise ValueError("Invalid numeric postal code")
                    values[7] = postal_code[:2] + "-" + postal_code[2:]
                seen_codes.add(values[0])
                rows.append(tuple(values))
            except ValueError as error:
                raise ValueError(f"Worksheet row {row_number + 1}: {error}") from error
        if not rows:
            raise ValueError("The contact worksheet has no nonempty data rows")
        return rows


def import_contacts(connection: psycopg.Connection, rows: list[tuple[str | None, ...]]) -> int:
    columns = list(SOURCE_COLUMNS.values())
    column_list = sql.SQL(", ").join(map(sql.Identifier, columns))
    assignments = sql.SQL(", ").join(
        sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(column))
        for column in columns[1:]
    )
    current_values = sql.SQL(", ").join(
        sql.Identifier("institution_contacts", column) for column in columns[1:]
    )
    new_values = sql.SQL(", ").join(
        sql.Identifier("excluded", column) for column in columns[1:]
    )
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('institution_contacts_seed', 0))")
        cursor.execute(sql.SQL(
            "CREATE TEMP TABLE staged_contacts ON COMMIT DROP AS "
            "SELECT {} FROM institution_contacts WITH NO DATA"
        ).format(column_list))
        with cursor.copy(sql.SQL("COPY staged_contacts ({}) FROM STDIN").format(column_list)) as copy:
            for row in rows:
                copy.write_row(row)
        cursor.execute(sql.SQL(
            "INSERT INTO institution_contacts ({columns}) "
            "SELECT {columns} FROM staged_contacts "
            "ON CONFLICT (teryt_code) DO UPDATE SET {assignments} "
            "WHERE ({current_values}) IS DISTINCT FROM ({new_values})"
        ).format(
            columns=column_list,
            assignments=assignments,
            current_values=current_values,
            new_values=new_values,
        ))
        return cursor.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    try:
        rows = read_contacts(args.workbook)
        # libpq reads PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD.
        with psycopg.connect(connect_timeout=10, autocommit=True) as connection:
            changed = import_contacts(connection, rows)
    except (OSError, ValueError, xlrd.XLRDError) as error:
        print(f"Contact import failed: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        # connection error messages can contain credentials or connection details.
        print(f"Contact import failed: database error ({error.sqlstate or 'connection failure'})", file=sys.stderr)
        return 1
    print(f"Imported {len(rows)} contacts ({changed} inserted or updated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
