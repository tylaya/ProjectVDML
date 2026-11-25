import asyncio
import json
import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException

import main


class RegistrationPeriodTests(unittest.TestCase):
    def test_registration_is_open_for_first_five_calendar_days_only(self):
        settings = {
            "semester_name": "2026/2027 - Ganjil",
            "semester_start_date": "2026-08-17",
        }

        self.assertTrue(main.registration_period(settings, date(2026, 8, 17))["is_open"])
        self.assertTrue(main.registration_period(settings, date(2026, 8, 21))["is_open"])
        self.assertFalse(main.registration_period(settings, date(2026, 8, 16))["is_open"])
        self.assertFalse(main.registration_period(settings, date(2026, 8, 22))["is_open"])

    def test_unconfigured_semester_closes_new_applications(self):
        payload = {
            "request_type": "Pendaftaran baru",
            "category": "Outsider Dekat",
            "residence_type": "Keluarga",
            "semester": "2026/2027 - Ganjil",
            "nama_mahasiswa": "Mahasiswa Test",
            "nama_kost": "Hunian Test",
            "alamat_kost": "Airmadidi",
            "kelurahan": "Airmadidi",
            "jarak_km": 3,
            "waktu_tempuh_menit": 10,
            "akses_jalan": "Jalan Utama",
        }

        with patch.object(
            main,
            "get_settings",
            return_value={"semester_name": "", "semester_start_date": None},
        ):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(
                    main.create_application_with_documents(
                        payload=json.dumps(payload),
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )

        self.assertEqual(error.exception.status_code, 403)
        self.assertIn("belum dikonfigurasi", error.exception.detail)

    def test_missing_semester_name_or_start_date_is_not_open(self):
        self.assertFalse(
            main.registration_period(
                {"semester_name": "2026/2027 - Ganjil", "semester_start_date": None},
                date(2026, 8, 17),
            )["is_open"]
        )


if __name__ == "__main__":
    unittest.main()
