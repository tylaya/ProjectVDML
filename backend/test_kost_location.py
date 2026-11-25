import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import main
from fastapi import HTTPException
from schemas import KostApproval, KostCreate, KostLocationUpdate


class KostLocationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "kost-location.sqlite3"
        self.database_patch = patch.object(database, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        database.init_db()
        self.admin = {"email": "admin@unklab.ac.id"}
        self.kost = KostCreate(
            name="Kost Satu",
            address="Airmadidi, Minahasa Utara",
            kelurahan="Airmadidi Bawah",
            residence_type="Kost putra",
            owner_email="owner@example.com",
            maps_url="https://www.google.com/maps/@-2,120,15z",
        )

    def tearDown(self):
        self.database_patch.stop()
        self.temporary_directory.cleanup()

    def test_out_of_province_kost_cannot_be_approved_or_listed(self):
        created = main.create_kost(self.kost, self.admin)

        self.assertTrue(created["location_anomaly"])
        with self.assertRaises(HTTPException) as error:
            main.decide_kost(
                created["id"], KostApproval(approval_status="Disetujui"), self.admin
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(main.list_approved_kosts({"email": "student@example.com"}), [])

    def test_correcting_kost_location_allows_approval_and_student_listing(self):
        created = main.create_kost(self.kost, self.admin)
        updated = main.update_kost_location(
            created["id"],
            KostLocationUpdate(
                maps_url="https://www.google.com/maps/@1.45,124.97,16z"
            ),
            self.admin,
        )
        self.assertEqual(updated["approval_status"], "Menunggu approval")
        approved = main.decide_kost(
            created["id"], KostApproval(approval_status="Disetujui"), self.admin
        )
        listed = main.list_approved_kosts({"email": "student@example.com"})

        self.assertFalse(updated["location_anomaly"])
        self.assertEqual(approved["approval_status"], "Disetujui")
        self.assertEqual([kost["id"] for kost in listed], [created["id"]])


if __name__ == "__main__":
    unittest.main()
