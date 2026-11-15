import json
import logging
import sqlite3
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database import get_connection, get_settings, init_db, save_settings
from schemas import InspectionInput, InspectionResult, Settings, Student, StudentCreate, StudentUpdate


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "ml" / "artifacts" / "housing_model.joblib"
METRICS_PATH = ROOT / "ml" / "artifacts" / "model_metrics.json"
FEATURES = ["jarak_km", "waktu_tempuh_menit", "kelurahan", "akses_jalan"]
model = None
model_metrics = None
model_error = None
logger = logging.getLogger(__name__)


def load_model():
    global model, model_metrics, model_error
    if not MODEL_PATH.exists() or not METRICS_PATH.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / "ml" / "train_model.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            model_error = f"Pelatihan model otomatis tidak dapat dijalankan: {error}"
            logger.error(model_error)
            return
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "Tidak ada detail tambahan."
            model_error = (
                "Model belum tersedia dan pelatihan otomatis gagal. "
                "Periksa dependensi ML atau jalankan `python ml/train_model.py` dari root proyek. "
                f"Detail: {detail}"
            )
            logger.error(model_error)
            return
    try:
        loaded_model = joblib.load(MODEL_PATH)
        loaded_metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except (OSError, EOFError, ImportError, ValueError) as error:
        model_error = f"Model ML gagal dimuat: {error}"
        logger.error(model_error)
        return
    if not hasattr(loaded_model, "predict_proba"):
        model_error = "Model tersimpan tidak mendukung estimasi confidence."
        logger.error(model_error)
        return
    model = loaded_model
    model_metrics = loaded_metrics
    model_error = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    load_model()
    yield


app = FastAPI(title="Village Dean Housing Verification API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)


def as_dict(row):
    return dict(row)


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": model is not None, "model_error": model_error}


@app.get("/api/dashboard")
def dashboard():
    with get_connection() as connection:
        total_students = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        category_rows = connection.execute(
            "SELECT kategori_terdaftar, COUNT(*) AS count FROM students GROUP BY kategori_terdaftar"
        ).fetchall()
        category_distribution = {"Outsider Dekat": 0, "Outsider Jauh": 0}
        category_distribution.update({row["kategori_terdaftar"]: row["count"] for row in category_rows})
        status_rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM inspections GROUP BY status"
        ).fetchall()
        status_distribution = {
            "Sesuai Kategori": 0,
            "Berpotensi Tidak Sesuai": 0,
            "Perlu Verifikasi Petugas": 0,
        }
        status_distribution.update({row["status"]: row["count"] for row in status_rows})
        total_inspections = connection.execute("SELECT COUNT(*) FROM inspections").fetchone()[0]
        recent = connection.execute(
            "SELECT * FROM inspections ORDER BY id DESC LIMIT 5"
        ).fetchall()
    return {
        "total_mahasiswa": total_students,
        "outsider_dekat": category_distribution["Outsider Dekat"],
        "outsider_jauh": category_distribution["Outsider Jauh"],
        "total_pemeriksaan": total_inspections,
        "perlu_verifikasi": (
            status_distribution["Berpotensi Tidak Sesuai"]
            + status_distribution["Perlu Verifikasi Petugas"]
        ),
        "distribusi_kategori": category_distribution,
        "distribusi_status": status_distribution,
        "pemeriksaan_terbaru": [as_dict(row) for row in recent],
    }


@app.get("/api/students", response_model=list[Student])
def list_students(search: str = Query(default="", max_length=120), category: str = ""):
    query = "SELECT * FROM students WHERE 1=1"
    parameters = []
    if search.strip():
        query += " AND (id LIKE ? OR nama_mahasiswa LIKE ? OR nama_kost LIKE ? OR kelurahan LIKE ?)"
        term = f"%{search.strip()}%"
        parameters.extend([term] * 4)
    if category in ("Outsider Dekat", "Outsider Jauh"):
        query += " AND kategori_terdaftar = ?"
        parameters.append(category)
    query += " ORDER BY id"
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [as_dict(row) for row in rows]


@app.post("/api/students", response_model=Student, status_code=201)
def create_student(student: StudentCreate):
    try:
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO students
                (id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan, jarak_km, kategori_terdaftar)
                VALUES (:id, :nama_mahasiswa, :nama_kost, :alamat_kost, :kelurahan, :jarak_km, :kategori_terdaftar)""",
                student.model_dump(),
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(status_code=409, detail="ID mahasiswa tersebut sudah digunakan.") from error
        raise
    return student


@app.put("/api/students/{student_id}", response_model=Student)
def update_student(student_id: str, student: StudentUpdate):
    with get_connection() as connection:
        cursor = connection.execute(
            """UPDATE students SET nama_mahasiswa=:nama_mahasiswa, nama_kost=:nama_kost,
            alamat_kost=:alamat_kost, kelurahan=:kelurahan, jarak_km=:jarak_km,
            kategori_terdaftar=:kategori_terdaftar WHERE id=:id""",
            {**student.model_dump(), "id": student_id},
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data mahasiswa tidak ditemukan.")
    return {"id": student_id, **student.model_dump()}


@app.delete("/api/students/{student_id}")
def delete_student(student_id: str):
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data mahasiswa tidak ditemukan.")
    return {"message": "Data mahasiswa berhasil dihapus. Riwayat pemeriksaan tetap tersimpan."}


@app.post("/api/inspections/analyze", response_model=InspectionResult, status_code=201)
def analyze_inspection(payload: InspectionInput):
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=model_error or "Model ML belum siap. Pemeriksaan tidak dapat dianalisis.",
        )
    settings = get_settings()
    sample = pd.DataFrame([{name: getattr(payload, name) for name in FEATURES}], columns=FEATURES)
    probabilities = model.predict_proba(sample)[0]
    best_index = int(probabilities.argmax())
    predicted = str(model.classes_[best_index])
    confidence = float(probabilities[best_index])
    mismatch = payload.kategori_terdaftar != predicted
    near_boundary = (
        settings["verification_zone_enabled"]
        and abs(payload.jarak_km - settings["distance_threshold_km"])
        <= settings["verification_zone_km"]
    )
    low_confidence = confidence < settings["confidence_threshold"]
    if near_boundary or low_confidence:
        status = "Perlu Verifikasi Petugas"
        reasons = []
        if near_boundary:
            reasons.append("jarak berada dalam zona verifikasi")
        if low_confidence:
            reasons.append("confidence model di bawah ambang pengaturan")
        explanation = f"Hasil model memerlukan peninjauan petugas karena {' dan '.join(reasons)}."
    elif mismatch:
        status = "Berpotensi Tidak Sesuai"
        explanation = (
            f"Prediksi model ({predicted}) berbeda dari kategori terdaftar "
            f"({payload.kategori_terdaftar}); pemeriksaan administratif lanjutan disarankan."
        )
    else:
        status = "Sesuai Kategori"
        explanation = (
            f"Prediksi model ({predicted}) konsisten dengan kategori terdaftar. "
            "Hasil ini merupakan rekomendasi pendukung verifikasi."
        )
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    values = {
        **payload.model_dump(),
        "prediksi_kategori": predicted,
        "confidence_score": confidence,
        "status": status,
        "keterangan": explanation,
        "tanggal_pemeriksaan": checked_at,
    }
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO inspections (
                student_id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan,
                jarak_km, waktu_tempuh_menit, akses_jalan, kategori_terdaftar,
                prediksi_kategori, confidence_score, status, keterangan, tanggal_pemeriksaan
            ) VALUES (
                :student_id, :nama_mahasiswa, :nama_kost, :alamat_kost, :kelurahan,
                :jarak_km, :waktu_tempuh_menit, :akses_jalan, :kategori_terdaftar,
                :prediksi_kategori, :confidence_score, :status, :keterangan, :tanggal_pemeriksaan
            )""",
            values,
        )
        values["id"] = cursor.lastrowid
    return values


@app.get("/api/inspections", response_model=list[InspectionResult])
def list_inspections(
    search: str = Query(default="", max_length=120),
    status: str = Query(default=""),
):
    query = "SELECT * FROM inspections WHERE 1=1"
    parameters = []
    if search.strip():
        query += " AND (student_id LIKE ? OR nama_mahasiswa LIKE ? OR nama_kost LIKE ?)"
        term = f"%{search.strip()}%"
        parameters.extend([term] * 3)
    if status in ("Sesuai Kategori", "Berpotensi Tidak Sesuai", "Perlu Verifikasi Petugas"):
        query += " AND status = ?"
        parameters.append(status)
    query += " ORDER BY id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [as_dict(row) for row in rows]


@app.get("/api/settings", response_model=Settings)
def read_settings():
    return get_settings()


@app.put("/api/settings", response_model=Settings)
def update_settings(settings: Settings):
    return save_settings(settings.model_dump())


@app.get("/api/ml/info")
def ml_info():
    if model_metrics is None:
        return {
            "status": "unavailable",
            "model_name": "Model ML belum tersedia",
            "features": FEATURES,
            "metrics": None,
            "message": model_error or "Model ML belum berhasil dimuat.",
        }
    return {
        "status": "ready",
        "model_name": model_metrics["model_name"],
        "features": model_metrics["features"],
        "metrics": {
            key: model_metrics["metrics"][key]
            for key in ("accuracy", "precision", "recall", "f1_score")
        },
    }
