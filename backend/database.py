import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


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
                kategori_terdaftar TEXT NOT NULL
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
                tanggal_pemeriksaan TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            seed_students(connection)
        if connection.execute("SELECT COUNT(*) FROM inspections").fetchone()[0] == 0:
            seed_inspections(connection)
        if connection.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                [(key, json.dumps(value, ensure_ascii=False)) for key, value in DEFAULT_SETTINGS.items()],
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
        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?)",
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
