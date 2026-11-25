import csv
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from location_analysis import is_in_north_sulawesi, parse_google_maps_coordinates


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("VILLAGE_DEAN_DB", BASE_DIR / "housing.db"))
DEFAULT_SETTINGS = {
    "officer_name": "Petugas Demo",
    "officer_title": "Verifikator Hunian",
    "officer_unit": "Village Dean — Universitas Klabat",
    "confidence_threshold": 0.65,
    "distance_threshold_km": 2.0,
    "verification_zone_km": 0.2,
    "verification_zone_enabled": True,
    "semester_name": "",
    "semester_start_date": None,
    "campus_maps_url": "",
}


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                nama_mahasiswa TEXT NOT NULL,
                nama_kost TEXT NOT NULL,
                alamat_kost TEXT NOT NULL,
                kelurahan TEXT NOT NULL,
                jarak_km REAL NOT NULL,
                kategori_terdaftar TEXT NOT NULL,
                maps_url TEXT NOT NULL DEFAULT '',
                location_anomaly INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                nama_mahasiswa TEXT NOT NULL,
                nama_kost TEXT NOT NULL,
                alamat_kost TEXT NOT NULL,
                kelurahan TEXT NOT NULL,
                jarak_km REAL NOT NULL,
                waktu_tempuh_menit INTEGER NOT NULL,
                akses_jalan TEXT NOT NULL,
                kategori_terdaftar TEXT NOT NULL,
                prediksi_kategori TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                status TEXT NOT NULL,
                keterangan TEXT NOT NULL,
                tanggal_pemeriksaan TEXT NOT NULL,
                maps_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('student', 'admin')),
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                password_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS kosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                kelurahan TEXT NOT NULL,
                residence_type TEXT NOT NULL CHECK (residence_type IN ('Kost putra', 'Kost putri')),
                owner_email TEXT NOT NULL,
                approval_status TEXT NOT NULL DEFAULT 'Menunggu approval'
                    CHECK (approval_status IN ('Menunggu approval', 'Disetujui', 'Ditolak')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                maps_url TEXT NOT NULL DEFAULT '',
                location_anomaly INTEGER NOT NULL DEFAULT 0,
                UNIQUE (name, address)
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_email TEXT NOT NULL REFERENCES users(email),
                request_type TEXT NOT NULL,
                category TEXT NOT NULL,
                residence_type TEXT NOT NULL,
                kost_id INTEGER REFERENCES kosts(id),
                kost_confirmation_status TEXT NOT NULL DEFAULT 'Tidak diperlukan',
                kost_confirmation_note TEXT NOT NULL DEFAULT '',
                semester TEXT NOT NULL,
                nama_mahasiswa TEXT NOT NULL DEFAULT '',
                nama_kost TEXT NOT NULL DEFAULT '',
                alamat_kost TEXT NOT NULL DEFAULT '',
                maps_url TEXT NOT NULL DEFAULT '',
                kelurahan TEXT NOT NULL DEFAULT '',
                jarak_km REAL NOT NULL DEFAULT 0,
                waktu_tempuh_menit INTEGER NOT NULL DEFAULT 0,
                akses_jalan TEXT NOT NULL DEFAULT '',
                ml_prediction TEXT NOT NULL DEFAULT '',
                ml_confidence REAL NOT NULL DEFAULT 0,
                ml_status TEXT NOT NULL DEFAULT '',
                ml_eligible INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Menunggu verifikasi',
                admin_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_email TEXT NOT NULL,
                action TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                email TEXT PRIMARY KEY REFERENCES users(email) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS application_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                document_type TEXT NOT NULL CHECK (
                    document_type IN (
                        'ktp', 'kartu_keluarga', 'surat_penerimaan_kost', 'surat_domisili'
                    )
                ),
                storage_key TEXT NOT NULL UNIQUE,
                content_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (application_id, document_type)
            );
            """
        )
        document_table = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'application_documents'"
        ).fetchone()
        if document_table and "surat_domisili" not in document_table["sql"]:
            connection.executescript(
                """
                CREATE TABLE application_documents_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    document_type TEXT NOT NULL CHECK (
                        document_type IN (
                            'ktp', 'kartu_keluarga', 'surat_penerimaan_kost', 'surat_domisili'
                        )
                    ),
                    storage_key TEXT NOT NULL UNIQUE,
                    content_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (application_id, document_type)
                );
                INSERT INTO application_documents_new
                    (id, application_id, document_type, storage_key, content_type, created_at)
                SELECT id, application_id, document_type, storage_key, content_type, created_at
                FROM application_documents;
                DROP TABLE application_documents;
                ALTER TABLE application_documents_new RENAME TO application_documents;
                """
            )
        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)")
        }
        if "password_hash" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        for table in ("students", "inspections", "kosts", "applications"):
            columns = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
            }
            if "maps_url" not in columns:
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN maps_url TEXT NOT NULL DEFAULT ''"
                )
        kost_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(kosts)")
        }
        if "location_anomaly" not in kost_columns:
            connection.execute(
                "ALTER TABLE kosts ADD COLUMN location_anomaly INTEGER NOT NULL DEFAULT 0"
            )
            for kost in connection.execute("SELECT id, maps_url FROM kosts").fetchall():
                try:
                    coordinates = parse_google_maps_coordinates(kost["maps_url"])
                    anomaly = not is_in_north_sulawesi(*coordinates)
                except ValueError:
                    anomaly = True
                connection.execute(
                    "UPDATE kosts SET location_anomaly = ? WHERE id = ?",
                    (anomaly, kost["id"]),
                )
        student_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(students)")
        }
        if "location_anomaly" not in student_columns:
            connection.execute(
                "ALTER TABLE students ADD COLUMN location_anomaly INTEGER NOT NULL DEFAULT 0"
            )
        application_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(applications)")
        }
        application_migrations = {
            "kost_id": "INTEGER REFERENCES kosts(id)",
            "kost_confirmation_status": "TEXT NOT NULL DEFAULT 'Tidak diperlukan'",
            "kost_confirmation_note": "TEXT NOT NULL DEFAULT ''",
            "nama_mahasiswa": "TEXT NOT NULL DEFAULT ''",
            "nama_kost": "TEXT NOT NULL DEFAULT ''",
            "alamat_kost": "TEXT NOT NULL DEFAULT ''",
            "kelurahan": "TEXT NOT NULL DEFAULT ''",
            "jarak_km": "REAL NOT NULL DEFAULT 0",
            "waktu_tempuh_menit": "INTEGER NOT NULL DEFAULT 0",
            "akses_jalan": "TEXT NOT NULL DEFAULT ''",
            "ml_prediction": "TEXT NOT NULL DEFAULT ''",
            "ml_confidence": "REAL NOT NULL DEFAULT 0",
            "ml_status": "TEXT NOT NULL DEFAULT ''",
            "ml_eligible": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in application_migrations.items():
            if column not in application_columns:
                connection.execute(
                    f"ALTER TABLE applications ADD COLUMN {column} {definition}"
                )
        sync_village_dean_students(connection)
        if connection.execute("SELECT COUNT(*) FROM inspections").fetchone()[0] == 0:
            seed_inspections(connection)
        if connection.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                [(key, json.dumps(value, ensure_ascii=False)) for key, value in DEFAULT_SETTINGS.items()],
            )


def sync_village_dean_students(connection):
    csv_path = BASE_DIR.parent / "ml" / "villagedean_dataset.csv"
    if not csv_path.exists():
        if connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            seed_students(connection)
        return

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    required = {"id_anonim", "nama_kost", "kelurahan", "jarak_km", "kategori_outsider"}
    if rows and required - set(rows[0].keys()):
        raise ValueError(
            f"Kolom dataset Village Dean tidak lengkap: {', '.join(sorted(required - set(rows[0].keys())))}"
        )
    if len(rows) == 0:
        raise ValueError("Dataset Village Dean tidak boleh kosong.")

    samples = []
    for row in rows:
        distance = float(row["jarak_km"])
        category = "Outsider Jauh" if distance > 2.0 else "Outsider Dekat"
        samples.append(
            (
                row["id_anonim"].strip(),
                f"Mahasiswa {row['id_anonim'].strip()}",
                row["nama_kost"].strip(),
                f"Area {row['kelurahan'].strip()}",
                row["kelurahan"].strip(),
                distance,
                category,
            )
        )
    connection.executemany(
        "INSERT OR REPLACE INTO students (id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan, jarak_km, kategori_terdaftar) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        samples,
    )


def seed_students(connection):
    samples = [
        ("VD-DEMO-001", "Mahasiswa Demo 01", "Kost Melati", "Area kampus Airmadidi", "Airmadidi Bawah", 0.8, "Outsider Dekat"),
        ("VD-DEMO-002", "Mahasiswa Demo 02", "Pondok Anggrek", "Airmadidi Atas", "Airmadidi Atas", 1.6, "Outsider Dekat"),
        ("VD-DEMO-003", "Mahasiswa Demo 03", "Kost Sukur", "Area Sukur", "Sukur", 3.5, "Outsider Jauh"),
        ("VD-DEMO-004", "Mahasiswa Demo 04", "Hunian Sarongsong", "Area Sarongsong", "Sarongsong", 2.4, "Outsider Jauh"),
        ("VD-DEMO-005", "Mahasiswa Demo 05", "Kost Rap-Rap", "Area Rap-Rap", "Rap-Rap", 4.6, "Outsider Jauh"),
        ("VD-DEMO-006", "Mahasiswa Demo 06", "Pondok Suwaan", "Area Suwaan", "Suwaan", 4.2, "Outsider Jauh"),
        ("VD-DEMO-007", "Mahasiswa Demo 07", "Kost Bawah", "Airmadidi Bawah", "Airmadidi Bawah", 1.3, "Outsider Dekat"),
        ("VD-DEMO-008", "Mahasiswa Demo 08", "Pondok Atas", "Airmadidi Atas", "Airmadidi Atas", 2.1, "Outsider Jauh"),
    ]
    connection.executemany(
        """INSERT INTO students (
            id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan,
            jarak_km, kategori_terdaftar
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        samples,
    )


def seed_inspections(connection):
    examples = [
        ("VD-DEMO-001", "Mahasiswa Demo 01", "Kost Melati", "Area kampus Airmadidi", "Airmadidi Bawah", 0.8, 5, "Jalan Utama", "Outsider Dekat", "Outsider Dekat", 0.94, "Sesuai Kategori", "Hasil demonstrasi awal; data sesuai dengan kategori terdaftar."),
        ("VD-DEMO-004", "Mahasiswa Demo 04", "Hunian Sarongsong", "Area Sarongsong", "Sarongsong", 2.4, 14, "Lorong", "Outsider Jauh", "Outsider Jauh", 0.71, "Perlu Verifikasi Petugas", "Contoh pemeriksaan dalam zona batas; konfirmasi informasi lokasi dianjurkan."),
        ("VD-DEMO-007", "Mahasiswa Demo 07", "Kost Bawah", "Airmadidi Bawah", "Airmadidi Bawah", 1.3, 8, "Jalan Utama", "Outsider Jauh", "Outsider Dekat", 0.91, "Berpotensi Tidak Sesuai", "Prediksi berbeda dari data terdaftar; pemeriksaan administratif lanjutan disarankan."),
    ]
    connection.executemany(
        """INSERT INTO inspections (
            student_id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan,
            jarak_km, waktu_tempuh_menit, akses_jalan, kategori_terdaftar,
            prediksi_kategori, confidence_score, status, keterangan, tanggal_pemeriksaan
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        examples,
    )


def get_settings(connection=None):
    if connection is not None:
        values = {
            row["key"]: json.loads(row["value"])
            for row in connection.execute("SELECT key, value FROM settings")
        }
        return {**DEFAULT_SETTINGS, **values}
    with get_connection() as active_connection:
        return get_settings(active_connection)


def save_settings(settings):
    with get_connection() as connection:
        connection.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(key, json.dumps(value, ensure_ascii=False)) for key, value in settings.items()],
        )
    return settings
