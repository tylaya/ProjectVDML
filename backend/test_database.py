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


if __name__ == "__main__":
    unittest.main()
