import json
import logging
import os
import sqlite3
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    clear_session_cookie,
    current_user,
    ensure_session_configuration,
    require_admin,
    require_student,
    set_session_cookie,
    verify_google_credential,
)
from database import get_connection, get_settings, init_db, save_settings
from schemas import (
    ApplicationCreate,
    ApplicationDecision,
    GoogleCredential,
    InspectionInput,
    InspectionResult,
    QueueSimulationRequest,
    Settings,
    Student,
    StudentCreate,
    StudentUpdate,
)


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.queue_modules import run_synthetic_week

load_dotenv(Path(__file__).resolve().parent / ".env")
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


app = FastAPI(title="SIGAP-VD Village Dean API", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ],
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


@app.post("/api/auth/google")
def login_with_google(payload: GoogleCredential, response: Response):
    ensure_session_configuration()
    user = verify_google_credential(
        payload.credential, payload.email, payload.requested_role
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO users (email, display_name, role, created_at, last_login_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                display_name=excluded.display_name,
                role=excluded.role,
                last_login_at=excluded.last_login_at""",
            (user["email"], user["name"], user["role"], now, now),
        )
        connection.execute(
            "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
            "VALUES (?, 'login', 'user', ?, ?)",
            (user["email"], user["email"], now),
        )
    set_session_cookie(response, user)
    return user


@app.get("/api/auth/me")
def read_current_user(user: dict = Depends(current_user)):
    return user


@app.post("/api/auth/logout")
def logout(response: Response, user: dict = Depends(current_user)):
    clear_session_cookie(response)
    return {"message": f"Sesi {user['email']} telah berakhir."}


@app.get("/api/applications/me")
def my_applications(user: dict = Depends(require_student)):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM applications WHERE student_email = ? ORDER BY id DESC",
            (user["email"],),
        ).fetchall()
    return [as_dict(row) for row in rows]


@app.post("/api/applications", status_code=201)
def create_application(payload: ApplicationCreate, user: dict = Depends(require_student)):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO applications (
                student_email, request_type, category, residence_type, semester, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user["email"],
                payload.request_type,
                payload.category,
                payload.residence_type,
                payload.semester.strip(),
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
            "VALUES (?, 'application_submitted', 'application', ?, ?)",
            (user["email"], str(cursor.lastrowid), now),
        )
        row = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return as_dict(row)


@app.get("/api/applications")
def list_applications(
    status: str = Query(default="", max_length=40),
    _user: dict = Depends(require_admin),
):
    valid_statuses = ("Menunggu verifikasi", "Perlu revisi", "Disetujui", "Ditolak")
    if status and status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Filter status pengajuan tidak dikenal.")
    query = "SELECT * FROM applications"
    parameters: tuple[str, ...] = ()
    if status in valid_statuses:
        query += " WHERE status = ?"
        parameters = (status,)
    query += " ORDER BY CASE status WHEN 'Menunggu verifikasi' THEN 0 ELSE 1 END, id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [as_dict(row) for row in rows]


@app.patch("/api/applications/{application_id}")
def decide_application(
    application_id: int,
    payload: ApplicationDecision,
    user: dict = Depends(require_admin),
):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            """UPDATE applications SET status = ?, admin_note = ?, updated_at = ?
            WHERE id = ?""",
            (payload.status, payload.admin_note.strip(), now, application_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan.")
        connection.execute(
            "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
            "VALUES (?, ?, 'application', ?, ?)",
            (user["email"], f"application_{payload.status.lower().replace(' ', '_')}", str(application_id), now),
        )
        row = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
    return as_dict(row)


@app.get("/api/dashboard")
def dashboard(_user: dict = Depends(require_admin)):
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
def list_students(
    search: str = Query(default="", max_length=120),
    category: str = "",
    _user: dict = Depends(require_admin),
):
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
def create_student(student: StudentCreate, _user: dict = Depends(require_admin)):
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
def update_student(student_id: str, student: StudentUpdate, _user: dict = Depends(require_admin)):
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
def delete_student(student_id: str, _user: dict = Depends(require_admin)):
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data mahasiswa tidak ditemukan.")
    return {"message": "Data mahasiswa berhasil dihapus. Riwayat pemeriksaan tetap tersimpan."}


@app.post("/api/inspections/analyze", response_model=InspectionResult, status_code=201)
def analyze_inspection(payload: InspectionInput, _user: dict = Depends(require_admin)):
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
    _user: dict = Depends(require_admin),
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
def read_settings(_user: dict = Depends(require_admin)):
    return get_settings()


@app.put("/api/settings", response_model=Settings)
def update_settings(settings: Settings, _user: dict = Depends(require_admin)):
    return save_settings(settings.model_dump())


@app.get("/api/ml/info")
def ml_info(_user: dict = Depends(require_admin)):
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


@app.post("/api/ml/queue-demo")
def queue_demo(
    payload: QueueSimulationRequest,
    _user: dict = Depends(require_admin),
):
    settings = get_settings()
    return run_synthetic_week(
        start_date=payload.start_date,
        service_counters=payload.service_counters,
        applicants_per_day=payload.applicants_per_day,
        seed=payload.seed,
        distance_threshold_km=settings["distance_threshold_km"],
        review_zone_km=settings["verification_zone_km"],
    )
