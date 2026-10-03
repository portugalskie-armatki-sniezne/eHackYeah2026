"""run inside the seed image; database checks use its PG environment variables."""

from contextlib import nullcontext
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import psycopg
import xlrd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tooling" / "seed"))
import import_institution_contacts as importer


class ContactImportTests(unittest.TestCase):
    def test_cell_values_preserve_text_and_remove_numeric_decimal_suffix(self):
        for cell, expected in [
            (xlrd.sheet.Cell(xlrd.XL_CELL_TEXT, " 0123456 "), "0123456"),
            (xlrd.sheet.Cell(xlrd.XL_CELL_NUMBER, 6484800.0), "6484800"),
            (xlrd.sheet.Cell(xlrd.XL_CELL_NUMBER, 30.65), "30.65"),
            (xlrd.sheet.Cell(xlrd.XL_CELL_TEXT, "12A/3"), "12A/3"),
            (xlrd.sheet.Cell(xlrd.XL_CELL_TEXT, "\u00a0"), None),
            (xlrd.sheet.Cell(xlrd.XL_CELL_EMPTY, ""), None),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(importer.cell_text(cell), expected)
        for cell_type, value in [(xlrd.XL_CELL_ERROR, 7), (xlrd.XL_CELL_DATE, 45000.0),
                                 (xlrd.XL_CELL_NUMBER, float("nan"))]:
            with self.assertRaises(ValueError):
                importer.cell_text(xlrd.sheet.Cell(cell_type, value))

    def read_fake(self, headers, rows):
        class Sheet:
            nrows = len(rows) + 1

            def row_values(self, index):
                return headers if index == 0 else rows[index - 1]

            def cell(self, row, column):
                value = rows[row - 1][column]
                kind = xlrd.XL_CELL_NUMBER if isinstance(value, float) else xlrd.XL_CELL_TEXT
                return xlrd.sheet.Cell(kind, value)

        class Workbook:
            nsheets = 1

            def sheet_by_index(self, index):
                return Sheet()

        with patch.object(importer.xlrd, "open_workbook", return_value=nullcontext(Workbook())):
            return importer.read_contacts(Path("test.xls"))

    def test_headers_reordering_and_numeric_codes(self):
        headers = list(importer.SOURCE_COLUMNS)
        row = ["201011", " Example "] + [""] * 20
        row[0], row[7] = 201011.0, 1234.0
        values = self.read_fake(headers[::-1], [row[::-1]])[0]
        self.assertEqual(values[0], "0201011")
        self.assertEqual(values[1], "Example")
        self.assertEqual(values[7], "01-234")

    def test_invalid_input_is_rejected(self):
        headers = list(importer.SOURCE_COLUMNS)
        row = ["1201000", "Example"] + [""] * 20
        cases = [
            (headers[:-1], [row[:-1]]),
            (headers, [row, row]),
            (headers, [["invalid", "Example"] + [""] * 20]),
            (headers, [["1201000"] + [""] * 21]),
            (headers, [[""] * 22]),
        ]
        for columns, rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.read_fake(columns, rows)

    def test_real_workbook(self):
        rows = importer.read_contacts(Path("/seeds/teleaddr_base_16042026.xls"))
        self.assertEqual(len(rows), 203)
        rzezawa = next(row for row in rows if row[0] == "1201072")
        self.assertEqual(rzezawa[1], "Rzezawa")
        self.assertEqual(rzezawa[12], "6484800")
        self.assertEqual(rzezawa[14], None)
        self.assertEqual(rows[129][14], "30.65")

    def test_atomic_upsert_and_unchanged_import(self):
        rows = importer.read_contacts(Path("/seeds/teleaddr_base_16042026.xls"))
        with psycopg.connect(autocommit=True) as connection:
            self.assertEqual(importer.import_contacts(connection, rows), 0)
            original_id = connection.execute(
                "SELECT id FROM institution_contacts WHERE teryt_code = %s", (rows[0][0],)
            ).fetchone()[0]
            changed = list(rows[0])
            changed[18] = "changed@example.invalid"
            self.assertEqual(importer.import_contacts(connection, [tuple(changed)]), 1)
            self.assertEqual(connection.execute(
                "SELECT id FROM institution_contacts WHERE teryt_code = %s", (rows[0][0],)
            ).fetchone()[0], original_id)
            invalid = list(rows[1])
            invalid[0] = "invalid"
            changed[18] = "must-rollback@example.invalid"
            with self.assertRaises(psycopg.errors.CheckViolation):
                importer.import_contacts(connection, [tuple(changed), tuple(invalid)])
            self.assertEqual(connection.execute(
                "SELECT email FROM institution_contacts WHERE id = %s", (original_id,)
            ).fetchone()[0], "changed@example.invalid")
            self.assertEqual(importer.import_contacts(connection, rows), 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM institution_contacts").fetchone()[0], 203)


if __name__ == "__main__":
    unittest.main()
