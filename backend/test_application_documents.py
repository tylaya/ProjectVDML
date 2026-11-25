import asyncio
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.datastructures import UploadFile

import database
import main
from document_storage import read_document, store_document, validate_document


class ApplicationDocumentTests(unittest.TestCase):
    def setUp(self):
        today = datetime.now(timezone(timedelta(hours=8))).date()
        self.settings_patch = patch.object(
            main,
            "get_settings",
            return_value={
                **database.DEFAULT_SETTINGS,
                "semester_name": "2026/2027 - Ganjil",
                "semester_start_date": today.isoformat(),
                "campus_maps_url": "https://www.google.com/maps/@1.45,124.97,16z",
            },
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def test_file_validation_checks_extension_and_signature(self):
        self.assertEqual(validate_document("id.pdf", b"%PDF-1.7 data"), "application/pdf")
        with self.assertRaises(ValueError):
            validate_document("id.pdf", b"not a pdf")
        with self.assertRaises(ValueError):
            validate_document("id.exe", b"MZ")

    def test_stored_file_is_encrypted_and_can_be_read_back(self):
        content = b"%PDF-1.7 private document"
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "DOCUMENT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "DOCUMENT_STORAGE_DIR": directory,
            },
        ):
            storage_key = store_document(content)
            encrypted = (Path(directory) / storage_key).read_bytes()

            self.assertNotEqual(encrypted, content)
            self.assertEqual(read_document(storage_key), content)
            with self.assertRaises(ValueError):
                read_document(f"../{storage_key}")

    def test_applications_require_residence_proof_and_far_requires_identity_documents(self):
        far_payload = self.payload("Outsider Jauh")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                main.create_application_with_documents(
                    payload=json.dumps(far_payload),
                    ktp=None,
                    kartu_keluarga=None,
                    user={"email": "s12345678@student.unklab.ac.id"},
                )
            )
        self.assertEqual(error.exception.status_code, 422)
        incomplete_uploads = (
            (None, UploadFile(filename="kk.pdf", file=io.BytesIO(b"%PDF-1.7 KK"))),
            (UploadFile(filename="ktp.pdf", file=io.BytesIO(b"%PDF-1.7 KTP")), None),
        )
        for ktp, kartu_keluarga in incomplete_uploads:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(
                    main.create_application_with_documents(
                        payload=json.dumps(far_payload),
                        ktp=ktp,
                        kartu_keluarga=kartu_keluarga,
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )
            self.assertEqual(error.exception.status_code, 422)

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "housing.sqlite3"
            storage_directory = Path(directory) / "documents"
            environment = {
                "DOCUMENT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "DOCUMENT_STORAGE_DIR": str(storage_directory),
            }
            with patch.object(database, "DATABASE_PATH", database_path), patch.dict(
                os.environ, environment
            ):
                database.init_db()
                with database.get_connection() as connection:
                    connection.execute(
                        """INSERT INTO users (
                            email, display_name, role, created_at, last_login_at
                        ) VALUES (?, ?, 'student', 'now', 'now')""",
                        ("s12345678@student.unklab.ac.id", "Test Student"),
                    )

                uploaded = asyncio.run(
                    main.create_application_with_documents(
                        payload=json.dumps(self.payload("Outsider Jauh")),
                        ktp=UploadFile(
                            filename="ktp.pdf",
                            file=io.BytesIO(b"%PDF-1.7 KTP"),
                        ),
                        kartu_keluarga=UploadFile(
                            filename="kk.png",
                            file=io.BytesIO(b"\x89PNG\r\n\x1a\nKK"),
                        ),
                        surat_domisili=UploadFile(
                            filename="domisili.pdf",
                            file=io.BytesIO(b"%PDF-1.7 Domisili"),
                        ),
                        surat_penerimaan_kost=None,
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )
                self.assertEqual(
                    set(uploaded["documents"]),
                    {"ktp", "kartu_keluarga", "surat_domisili"},
                )

                with self.assertRaises(HTTPException) as error:
                    asyncio.run(
                        main.create_application_with_documents(
                            payload=json.dumps(self.payload("Outsider Dekat")),
                            ktp=None,
                            kartu_keluarga=None,
                            surat_domisili=UploadFile(
                                filename="domisili.pdf",
                                file=io.BytesIO(b"%PDF-1.7 Domisili"),
                            ),
                            surat_penerimaan_kost=None,
                            user={"email": "s12345678@student.unklab.ac.id"},
                        )
                    )
                self.assertEqual(error.exception.status_code, 422)

                near = asyncio.run(
                    main.create_application_with_documents(
                        payload=json.dumps(self.payload("Outsider Dekat")),
                        ktp=UploadFile(
                            filename="ktp-near.pdf",
                            file=io.BytesIO(b"%PDF-1.7 KTP near"),
                        ),
                        kartu_keluarga=UploadFile(
                            filename="kk-near.pdf",
                            file=io.BytesIO(b"%PDF-1.7 KK near"),
                        ),
                        surat_domisili=UploadFile(
                            filename="domisili.pdf",
                            file=io.BytesIO(b"%PDF-1.7 Domisili"),
                        ),
                        surat_penerimaan_kost=None,
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )
                self.assertEqual(
                    set(near["documents"]),
                    {"ktp", "kartu_keluarga", "surat_domisili"},
                )
                with database.get_connection() as connection:
                    records = connection.execute(
                        "SELECT storage_key, document_type FROM application_documents"
                    ).fetchall()
                self.assertEqual(len(records), 6)
                self.assertIn(
                    read_document(records[0]["storage_key"]),
                    (
                        b"%PDF-1.7 KTP",
                        b"\x89PNG\r\n\x1a\nKK",
                        b"%PDF-1.7 Domisili",
                    ),
                )

    def test_kost_application_must_use_approved_matching_listing_and_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "housing.sqlite3"
            with patch.object(database, "DATABASE_PATH", database_path), patch.dict(
                os.environ,
                {
                    "DOCUMENT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                    "DOCUMENT_STORAGE_DIR": str(Path(directory) / "documents"),
                },
            ):
                database.init_db()
                with database.get_connection() as connection:
                    connection.execute(
                        """INSERT INTO users (
                            email, display_name, role, created_at, last_login_at
                        ) VALUES (?, ?, 'student', 'now', 'now')""",
                        ("s12345678@student.unklab.ac.id", "Test Student"),
                    )
                    cursor = connection.execute(
                        """INSERT INTO kosts (
                            name, address, kelurahan, residence_type, owner_email,
                            approval_status, created_at, updated_at, maps_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            "Kost Test",
                            "Jalan Kampus 1",
                            "Airmadidi",
                            "Kost putra",
                            "owner@example.com",
                            "Menunggu approval",
                            "now",
                            "now",
                            "https://www.google.com/maps/@1.45,124.97,16z",
                        ),
                    )
                    kost_id = cursor.lastrowid
                application_payload = self.payload("Outsider Dekat")
                application_payload.update(
                    {
                        "residence_type": "Kost putra",
                        "kost_id": kost_id,
                    }
                )
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(
                        main.create_application_with_documents(
                            payload=json.dumps(application_payload),
                            ktp=None,
                            kartu_keluarga=None,
                            surat_penerimaan_kost=UploadFile(
                                filename="bukti.pdf",
                                file=io.BytesIO(b"%PDF-1.7 Terdaftar"),
                            ),
                            surat_domisili=None,
                            user={"email": "s12345678@student.unklab.ac.id"},
                        )
                    )
                self.assertEqual(error.exception.status_code, 422)
                with database.get_connection() as connection:
                    connection.execute(
                        "UPDATE kosts SET approval_status = 'Disetujui' WHERE id = ?",
                        (kost_id,),
                    )
                result = asyncio.run(
                    main.create_application_with_documents(
                        payload=json.dumps(application_payload),
                        ktp=None,
                        kartu_keluarga=None,
                        surat_penerimaan_kost=UploadFile(
                            filename="bukti.pdf",
                            file=io.BytesIO(b"%PDF-1.7 Terdaftar"),
                        ),
                        surat_domisili=None,
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )
                self.assertEqual(result["nama_kost"], "Kost Test")
                self.assertEqual(result["kost_confirmation_status"], "Menunggu kost")
                self.assertEqual(result["documents"], ["surat_penerimaan_kost"])

    @staticmethod
    def payload(category):
        return {
            "request_type": "Pendaftaran baru",
            "category": category,
            "residence_type": "Keluarga",
            "semester": "2026/2027 - Ganjil",
            "nama_mahasiswa": "Mahasiswa Test",
            "nama_kost": "Hunian Test",
            "alamat_kost": "Airmadidi",
            "maps_url": "https://www.google.com/maps/@1.45,124.97,16z",
            "kelurahan": "Airmadidi",
            "jarak_km": 3,
            "waktu_tempuh_menit": 10,
            "akses_jalan": "Jalan Utama",
        }


if __name__ == "__main__":
    unittest.main()
