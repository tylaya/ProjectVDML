import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class UserPasswordMigrationTests(unittest.TestCase):
    def test_existing_users_table_gets_password_hash_column(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """CREATE TABLE users (
                        email TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_login_at TEXT NOT NULL
                    )"""
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(database, "DATABASE_PATH", database_path):
                database.init_db()
                with database.get_connection() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute("PRAGMA table_info(users)")
                    }

        self.assertIn("password_hash", columns)

    def test_existing_kost_locations_are_checked_during_anomaly_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """CREATE TABLE kosts (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        address TEXT NOT NULL,
                        kelurahan TEXT NOT NULL,
                        residence_type TEXT NOT NULL,
                        owner_email TEXT NOT NULL,
                        approval_status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        maps_url TEXT NOT NULL DEFAULT ''
                    )"""
                )
                connection.execute(
                    """INSERT INTO kosts VALUES (
                        1, 'Kost Luar', 'alamat', 'kelurahan', 'Kost putra',
                        'owner@example.com', 'Disetujui', 'now', 'now',
                        'https://www.google.com/maps/@-2,120,15z'
                    )"""
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(database, "DATABASE_PATH", database_path):
                database.init_db()
                with database.get_connection() as connection:
                    anomaly = connection.execute(
                        "SELECT location_anomaly FROM kosts WHERE id = 1"
                    ).fetchone()["location_anomaly"]

        self.assertEqual(anomaly, 1)

    def test_existing_application_documents_are_preserved_during_type_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE applications (id INTEGER PRIMARY KEY);
                    CREATE TABLE application_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                        document_type TEXT NOT NULL CHECK (document_type IN ('ktp', 'kartu_keluarga')),
                        storage_key TEXT NOT NULL UNIQUE,
                        content_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE (application_id, document_type)
                    );
                    INSERT INTO applications (id) VALUES (10);
                    INSERT INTO application_documents (
                        application_id, document_type, storage_key, content_type, created_at
                    ) VALUES (10, 'ktp', 'legacy-document.enc', 'application/pdf', 'now');
                    """
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(database, "DATABASE_PATH", database_path):
                database.init_db()
                with database.get_connection() as connection:
                    document = connection.execute(
                        "SELECT application_id, document_type, storage_key FROM application_documents"
                    ).fetchone()
                    schema = connection.execute(
                        "SELECT sql FROM sqlite_master WHERE name = 'application_documents'"
                    ).fetchone()["sql"]

        self.assertEqual(
            (document["application_id"], document["document_type"], document["storage_key"]),
            (10, "ktp", "legacy-document.enc"),
        )
        self.assertIn("surat_domisili", schema)


if __name__ == "__main__":
    unittest.main()
