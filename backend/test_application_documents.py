import asyncio
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.datastructures import UploadFile

import database
import main
from document_storage import read_document, store_document, validate_document


class ApplicationDocumentTests(unittest.TestCase):
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

    def test_far_application_requires_both_documents_and_near_needs_none(self):
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
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )
                self.assertEqual(set(uploaded["documents"]), {"ktp", "kartu_keluarga"})

                near = asyncio.run(
                    main.create_application_with_documents(
                        payload=json.dumps(self.payload("Outsider Dekat")),
                        ktp=None,
                        kartu_keluarga=None,
                        user={"email": "s12345678@student.unklab.ac.id"},
                    )
                )
                self.assertEqual(near["documents"], [])
                with database.get_connection() as connection:
                    records = connection.execute(
                        "SELECT storage_key, document_type FROM application_documents"
                    ).fetchall()
                self.assertEqual(len(records), 2)
                self.assertIn(
                    read_document(records[0]["storage_key"]),
                    (b"%PDF-1.7 KTP", b"\x89PNG\r\n\x1a\nKK"),
                )

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
            "kelurahan": "Airmadidi",
            "jarak_km": 3,
            "waktu_tempuh_menit": 10,
            "akses_jalan": "Jalan Utama",
        }


if __name__ == "__main__":
    unittest.main()
