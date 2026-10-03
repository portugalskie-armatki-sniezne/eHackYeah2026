"""check official service data, collection rules, and transactional seed updates."""

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tooling" / "seed"))
import collect_service_entities as collector
import import_local_government_offices as offices_importer
import import_reference_data as reference_importer
import import_service_entities as importer


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ServiceEntityImportTests(unittest.TestCase):
    def setUp(self):
        self.records = importer.read_entities(Path("/seeds/service_entities.json"))

    def test_real_snapshot_distinguishes_operators_and_managers(self):
        by_short_name = {record["short_name"]: record for record in self.records if record["short_name"]}
        for name, kind in {"ZDMK": "road_manager", "ZTP": "transport_authority",
                           "MPK": "transport_operator", "Mobilis": "transport_operator",
                           "MPO": "waste_management", "ZZM": "green_space_manager",
                           "ZIW": "water_infrastructure_manager", "WMK": "water_sewage_utility",
                           "MPEC": "heating_utility", "SMMK": "municipal_guard"}.items():
            with self.subTest(name=name):
                record = by_short_name[name]
                self.assertEqual(record["entity_type"], kind)
                self.assertTrue(record["reporting_channel"])
                self.assertTrue(record["source_urls"])
                self.assertEqual(record["teryt_code"], "1261011")
        self.assertTrue(any(record["teryt_code"] is None for record in self.records))

    def test_actual_bip_zip_filters_region_and_fire_brigades(self):
        data = (FIXTURES / "service_entities_bip.xml").read_bytes()
        zipped = BytesIO()
        with ZipFile(zipped, "w") as archive:
            archive.writestr("subjects.xml", data)
        records, count = collector.parse_bip(zipped.getvalue(), "2026-10-03")
        self.assertEqual(count, 6)
        self.assertEqual({record["source_key"] for record in records},
                         {"bip:129155", "bip:122809", "bip:102074", "bip:127777"})
        self.assertEqual(next(record for record in records if record["source_key"] == "bip:129155")["email"],
                         "sekretariat@ztp.krakow.pl")
        with self.assertRaises(ValueError):
            collector.parse_bip(b"<resultset/>", "2026-10-03")
        with self.assertRaises(ValueError):
            collector.parse_bip(b'<!DOCTYPE resultset><resultset/>', "2026-10-03")

    def test_real_regional_contact_and_archive_rejection(self):
        article = json.loads((FIXTURES / "service_entity_article.json").read_text())
        contacts = collector.article_contacts(article)
        self.assertEqual(contacts["email"], "straz@wieliczka.eu")
        self.assertEqual(contacts["phone_number"], "+48122782105")
        self.assertEqual(contacts["locality"], "Wieliczka")
        self.assertEqual(contacts["house_number"], "2")
        self.assertNotIn("reporting_channel", contacts)
        article["isArchived"] = True
        with self.assertRaises(ValueError):
            collector.article_contacts(article)

    def test_html_headings_do_not_join_email_and_next_label(self):
        article = json.loads((FIXTURES / "service_entity_contact.json").read_text())
        self.assertEqual(collector.article_contacts(article)["email"], "biuro@gzwik-bochnia.pl")

    def test_merge_preserves_identity_and_supplement_verification_date(self):
        central = next(record for record in self.records if record["source_key"] == "bip:131102")
        regional = deepcopy(central)
        regional["source_key"] = "malopolska:224"
        regional["bip_url"] = "http://bip.malopolska.pl/pzdnowysacz/"
        supplement = {"source_key": central["source_key"], "short_name": "PZD",
                      "source_urls": ["https://bip.malopolska.pl/pzdnowysacz"], "verified_on": "2026-10-01"}
        merged = collector.merge_records([central], [regional], [supplement], [regional])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source_key"], "malopolska:224")
        self.assertEqual(merged[0]["verified_on"], "2026-10-01")
        self.assertEqual(merged[0]["short_name"], "PZD")

    def test_invalid_input_is_rejected_before_import(self):
        for field, value in [("teryt_code", "12"), ("name", " "), ("entity_type", "operator"),
                             ("source_urls", []), ("source_urls", ["file:///etc/passwd"]),
                             ("verified_on", "invalid"), ("reporting_channel", "javascript:alert(1)")]:
            with self.subTest(field=field):
                record = deepcopy(self.records[0])
                record[field] = value
                with self.assertRaises(ValueError):
                    importer.validate_entities([record])
        with self.assertRaises(ValueError):
            importer.validate_entities([self.records[0], self.records[0]])

    def test_missing_contact_fields_remain_null(self):
        record = deepcopy(self.records[0])
        required = {"source_key", "name", "entity_type", "source_urls", "verified_on"}
        for field in set(importer.COLUMNS) - required:
            record[field] = None
        with psycopg.connect(autocommit=True) as connection:
            try:
                importer.import_entities(connection, [record])
                stored = connection.execute(
                    "SELECT teryt_code, email, phone_number, website, bip_url, reporting_channel "
                    "FROM service_entities WHERE source_key = %s", (record["source_key"],)
                ).fetchone()
                self.assertEqual(stored, (None,) * 6)
                record["reporting_channel"] = "tel:986"
                importer.import_entities(connection, [record])
                self.assertIsNone(connection.execute(
                    "SELECT reporting_channel_description FROM service_entities WHERE source_key = %s",
                    (record["source_key"],)
                ).fetchone()[0])
            finally:
                importer.import_entities(connection, self.records)

    def test_upsert_ids_unchanged_rows_and_database_failure_rollback(self):
        with psycopg.connect(autocommit=True) as connection:
            self.assertEqual(importer.import_entities(connection, self.records), 0)
            first, second = deepcopy(self.records[:2])
            original_id = connection.execute(
                "SELECT id FROM service_entities WHERE source_key = %s", (first["source_key"],)
            ).fetchone()[0]
            first["name"] += " updated"
            self.assertEqual(importer.import_entities(connection, [first]), 1)
            self.assertEqual(connection.execute(
                "SELECT id FROM service_entities WHERE source_key = %s", (first["source_key"],)
            ).fetchone()[0], original_id)
            connection.execute("ALTER TABLE service_entities ADD CONSTRAINT test_seed_rollback "
                               "CHECK (name <> 'rollback sentinel')")
            try:
                second["name"] = "rollback sentinel"
                office = offices_importer.read_contacts(Path("/seeds/teleaddr_base_16042026.xls"))[0]
                changed_office = list(office)
                changed_office[15] = "rollback@example.invalid"
                with self.assertRaises(psycopg.errors.CheckViolation):
                    reference_importer.import_data(connection, [tuple(changed_office)], [self.records[0], second])
                self.assertEqual(connection.execute(
                    "SELECT name FROM service_entities WHERE id = %s", (original_id,)
                ).fetchone()[0], first["name"])
                self.assertEqual(connection.execute(
                    "SELECT email FROM local_government_offices WHERE teryt_code = %s", (office[0],)
                ).fetchone()[0], office[15])
            finally:
                connection.execute("ALTER TABLE service_entities DROP CONSTRAINT test_seed_rollback")
            self.assertEqual(importer.import_entities(connection, self.records), 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM service_entities").fetchone()[0],
                             len(self.records))


if __name__ == "__main__":
    unittest.main()
