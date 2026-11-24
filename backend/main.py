import json
import logging
import os
import sqlite3
import subprocess
import sys
from io import BytesIO
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from auth import (
    clear_session_cookie,
    current_user,
    ensure_session_configuration,
    hash_password,
    is_student_email,
    is_valid_password_hash,
    require_admin,
    require_student,
    set_session_cookie,
    verify_google_credential,
    verify_password,
)
from database import get_connection, get_settings, init_db, save_settings
from document_storage import (
    DOCUMENT_TYPES,
    MAX_DOCUMENT_SIZE,
    read_document,
    store_document,
    validate_document,
)
from schemas import (
    ApplicationCreate,
    ApplicationDecision,
    GoogleCredential,
    InspectionInput,
    InspectionResult,
    PasswordLogin,
    QueueSimulationRequest,
    Settings,
    StudentRegistration,
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
model_features = FEATURES
logger = logging.getLogger(__name__)


def model_accuracy() -> float:
    if not isinstance(model_metrics, dict):
        return 0.0
    metrics = model_metrics.get("metrics")
    if not isinstance(metrics, dict):
        return 0.0
    return max(0.0, min(1.0, float(metrics.get("accuracy", 0.0))))


def classify_distance(distance: float) -> str:
    return "Outsider Jauh" if float(distance) > 2.0 else "Outsider Dekat"


def load_model():
    global model, model_metrics, model_error, model_features
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
    model_features = loaded_metrics.get("features", FEATURES)
    model_error = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    load_model()
    yield


app = FastAPI(title="SIGAP-VD Village Dean API", version="1.1.0", lifespan=lifespan)
frontend_origins = {
    origin.strip()
    for origin in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
}
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").strip()
if frontend_url:
    frontend_origins.add(frontend_url)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)


def as_dict(row):
    return dict(row)


def record_login(user: dict[str, str], action: str = "login") -> None:
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
            "VALUES (?, ?, 'user', ?, ?)",
            (user["email"], action, user["email"], now),
        )


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": model is not None, "model_error": model_error}


@app.post("/api/auth/google")
def login_with_google(payload: GoogleCredential, request: Request, response: Response):
    ensure_session_configuration()
    user = verify_google_credential(
        payload.credential, payload.email, payload.requested_role
    )
    record_login(user)
    set_session_cookie(response, user, request)
    return user


@app.post("/api/auth/login")
def login_with_password(
    payload: PasswordLogin, request: Request, response: Response
):
    ensure_session_configuration()
    email = payload.email
    admin_emails = os.environ.get("ADMIN_EMAILS", "")
    allowed_admins = {
        item.strip().lower() for item in admin_emails.split(",") if item.strip()
    }

    if email in allowed_admins:
        admin_password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
        if not admin_password_hash or not is_valid_password_hash(admin_password_hash):
            raise HTTPException(
                status_code=503,
                detail="Kredensial admin belum dikonfigurasi dengan hash scrypt yang valid.",
            )
        if not verify_password(payload.password, admin_password_hash):
            raise HTTPException(status_code=401, detail="Email atau password tidak valid.")
        user = {"email": email, "name": "Admin Village Dean", "role": "admin"}
        record_login(user)
    else:
        if not is_student_email(email):
            raise HTTPException(
                status_code=403,
                detail="Gunakan email mahasiswa berformat s12345678@student.unklab.ac.id.",
            )
        with get_connection() as connection:
            row = connection.execute(
                "SELECT display_name, role, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if row is None:
                password_hash = hash_password(payload.password)
                display_name = "Mahasiswa " + email.split("@", 1)[0].upper()
                connection.execute(
                    """INSERT INTO users (
                        email, display_name, role, created_at, last_login_at, password_hash
                    ) VALUES (?, ?, 'student', ?, ?, ?)""",
                    (email, display_name, now, now, password_hash),
                )
                connection.execute(
                    "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
                    "VALUES (?, 'account_registered', 'user', ?, ?)",
                    (email, email, now),
                )
                user = {"email": email, "name": display_name, "role": "student"}
            else:
                if (
                    row["role"] != "student"
                    or not row["password_hash"]
                    or not verify_password(payload.password, row["password_hash"])
                ):
                    raise HTTPException(status_code=401, detail="Email atau password tidak valid.")
                user = {"email": email, "name": row["display_name"], "role": "student"}
                connection.execute(
                    "UPDATE users SET last_login_at = ? WHERE email = ?",
                    (now, email),
                )
            connection.execute(
                "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
                "VALUES (?, 'login', 'user', ?, ?)",
                (email, email, now),
            )

    set_session_cookie(response, user, request)
    return user


@app.post("/api/auth/register", status_code=201)
def register_student(
    payload: StudentRegistration, request: Request, response: Response
):
    ensure_session_configuration()
    email = payload.email
    allowed_admins = {
        item.strip().lower()
        for item in os.environ.get("ADMIN_EMAILS", "").split(",")
        if item.strip()
    }
    if email in allowed_admins:
        raise HTTPException(status_code=403, detail="Akun admin tidak dapat didaftarkan sebagai mahasiswa.")

    password_hash = hash_password(payload.password)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT role, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if existing is not None:
                if existing["role"] != "student":
                    raise HTTPException(
                        status_code=403,
                        detail="Email ini tidak dapat didaftarkan sebagai mahasiswa.",
                    )
                if existing["password_hash"]:
                    raise HTTPException(
                        status_code=409,
                        detail="Akun sudah terdaftar. Silakan masuk.",
                    )
                update = connection.execute(
                    """UPDATE users SET display_name = ?, password_hash = ?, last_login_at = ?
                    WHERE email = ? AND role = 'student' AND password_hash IS NULL""",
                    ("Mahasiswa " + email.split("@", 1)[0].upper(), password_hash, now, email),
                )
                if update.rowcount != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="Akun sudah terdaftar. Silakan masuk.",
                    )
            else:
                connection.execute(
                    """INSERT INTO users (
                        email, display_name, role, created_at, last_login_at, password_hash
                    ) VALUES (?, ?, 'student', ?, ?, ?)""",
                    (email, "Mahasiswa " + email.split("@", 1)[0].upper(), now, now, password_hash),
                )
            connection.execute(
                "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
                "VALUES (?, 'account_registered', 'user', ?, ?)",
                (email, email, now),
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: users.email" in str(error):
            raise HTTPException(
                status_code=409,
                detail="Akun sudah terdaftar. Silakan masuk.",
            ) from error
        raise

    user = {
        "email": email,
        "name": "Mahasiswa " + email.split("@", 1)[0].upper(),
        "role": "student",
    }
    set_session_cookie(response, user, request)
    return user


@app.get("/api/auth/me")
def read_current_user(user: dict = Depends(current_user)):
    return user


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user: dict = Depends(current_user)):
    clear_session_cookie(response, request)
    return {"message": f"Sesi {user['email']} telah berakhir."}


@app.get("/api/applications/me")
def my_applications(user: dict = Depends(require_student)):
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT applications.*,
                (SELECT group_concat(document_type, ',')
                 FROM application_documents
                 WHERE application_id = applications.id) AS document_types
                FROM applications WHERE student_email = ? ORDER BY id DESC""",
            (user["email"],),
        ).fetchall()
    return [application_record(row) for row in rows]


def application_record(row):
    record = as_dict(row)
    record["documents"] = (
        record.pop("document_types", "").split(",")
        if record.get("document_types")
        else []
    )
    return record


def insert_application(connection, payload: ApplicationCreate, user: dict, now: str):
    cursor = connection.execute(
        """INSERT INTO applications (
            student_email, request_type, category, residence_type, semester,
            nama_mahasiswa, nama_kost, alamat_kost, kelurahan, jarak_km,
            waktu_tempuh_menit, akses_jalan, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user["email"],
            payload.request_type,
            payload.category,
            payload.residence_type,
            payload.semester.strip(),
            payload.nama_mahasiswa.strip(),
            payload.nama_kost.strip(),
            payload.alamat_kost.strip(),
            payload.kelurahan.strip(),
            payload.jarak_km,
            payload.waktu_tempuh_menit,
            payload.akses_jalan,
            now,
            now,
        ),
    )
    connection.execute(
        "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
        "VALUES (?, 'application_submitted', 'application', ?, ?)",
        (user["email"], str(cursor.lastrowid), now),
    )
    return cursor.lastrowid


@app.post("/api/applications", status_code=201)
def create_application(payload: ApplicationCreate, user: dict = Depends(require_student)):
    if payload.category == "Outsider Jauh":
        raise HTTPException(
            status_code=422,
            detail="Pengajuan Outsider Jauh wajib menyertakan KTP dan Kartu Keluarga.",
        )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        application_id = insert_application(connection, payload, user, now)
        row = connection.execute(
            """SELECT applications.*, NULL AS document_types
               FROM applications WHERE id = ?""",
            (application_id,),
        ).fetchone()
    return application_record(row)


async def read_upload(document_type: str, upload: UploadFile | None):
    if upload is None:
        raise HTTPException(
            status_code=422,
            detail=f"Berkas {DOCUMENT_TYPES[document_type]} wajib diunggah untuk Outsider Jauh.",
        )
    data = await upload.read(MAX_DOCUMENT_SIZE + 1)
    if len(data) > MAX_DOCUMENT_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Ukuran berkas {DOCUMENT_TYPES[document_type]} maksimal 5 MB.",
        )
    try:
        content_type = validate_document(upload.filename or "", data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return data, content_type


@app.post("/api/applications/with-documents", status_code=201)
async def create_application_with_documents(
    payload: str = Form(...),
    ktp: UploadFile | None = File(default=None),
    kartu_keluarga: UploadFile | None = File(default=None),
    user: dict = Depends(require_student),
):
    try:
        application_payload = ApplicationCreate.model_validate_json(payload)
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=json.loads(error.json()),
        ) from error

    documents = {}
    if application_payload.category == "Outsider Jauh":
        for document_type, upload in (
            ("ktp", ktp),
            ("kartu_keluarga", kartu_keluarga),
        ):
            data, content_type = await read_upload(document_type, upload)
            documents[document_type] = (data, content_type)
    elif ktp is not None or kartu_keluarga is not None:
        raise HTTPException(
            status_code=422,
            detail="Berkas KTP dan Kartu Keluarga hanya diminta untuk Outsider Jauh.",
        )

    stored_documents = []
    try:
        for document_type, (data, content_type) in documents.items():
            try:
                storage_key = store_document(data)
            except RuntimeError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
            stored_documents.append(storage_key)
            documents[document_type] = (storage_key, content_type)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with get_connection() as connection:
            application_id = insert_application(
                connection, application_payload, user, now
            )
            for document_type, (storage_key, content_type) in documents.items():
                connection.execute(
                    """INSERT INTO application_documents (
                        application_id, document_type, storage_key, content_type, created_at
                    ) VALUES (?, ?, ?, ?, ?)""",
                    (
                        application_id,
                        document_type,
                        storage_key,
                        content_type,
                        now,
                    ),
                )
            row = connection.execute(
                """SELECT applications.*, ? AS document_types
                   FROM applications WHERE id = ?""",
                (",".join(documents), application_id),
            ).fetchone()
    except Exception:
        for storage_key in stored_documents:
            try:
                storage_directory = Path(
                    os.environ.get("DOCUMENT_STORAGE_DIR")
                    or Path(__file__).resolve().parent / "private_documents"
                )
                (storage_directory / storage_key).unlink(missing_ok=True)
            except OSError:
                logger.exception("Gagal membersihkan berkas pengajuan yang batal.")
        raise
    return application_record(row)


@app.get("/api/applications")
def list_applications(
    status: str = Query(default="", max_length=40),
    _user: dict = Depends(require_admin),
):
    valid_statuses = ("Menunggu verifikasi", "Perlu revisi", "Disetujui", "Ditolak")
    if status and status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Filter status pengajuan tidak dikenal.")
    query = """SELECT applications.*,
        (SELECT group_concat(document_type, ',')
         FROM application_documents
         WHERE application_id = applications.id) AS document_types
        FROM applications"""
    parameters: tuple[str, ...] = ()
    if status in valid_statuses:
        query += " WHERE status = ?"
        parameters = (status,)
    query += " ORDER BY CASE status WHEN 'Menunggu verifikasi' THEN 0 ELSE 1 END, id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [application_record(row) for row in rows]


@app.get("/api/applications/{application_id}/documents/{document_type}")
def download_application_document(
    application_id: int,
    document_type: str,
    _user: dict = Depends(require_admin),
):
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=404, detail="Jenis dokumen tidak ditemukan.")
    with get_connection() as connection:
        document = connection.execute(
            """SELECT storage_key, content_type FROM application_documents
               WHERE application_id = ? AND document_type = ?""",
            (application_id, document_type),
        ).fetchone()
    if document is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    try:
        content = read_document(document["storage_key"])
    except RuntimeError as error:
        logger.error("Dokumen pengajuan %s gagal dibaca: %s", application_id, error)
        raise HTTPException(status_code=503, detail=str(error)) from error
    extension = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }.get(document["content_type"])
    if extension is None:
        raise HTTPException(status_code=500, detail="Format dokumen tersimpan tidak dikenal.")
    return StreamingResponse(
        BytesIO(content),
        media_type=document["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{document_type}{extension}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/applications/{application_id}/analyze")
def analyze_application(
    application_id: int,
    _user: dict = Depends(require_admin),
):
    if model is None:
        raise HTTPException(status_code=503, detail=model_error or "Model ML belum siap.")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan.")
        application = as_dict(row)
        if not application["nama_mahasiswa"] or not application["jarak_km"]:
            raise HTTPException(
                status_code=422,
                detail="Pengajuan lama belum memiliki data hunian dan jarak untuk dianalisis.",
            )
        inspection_values = {
            "jarak_km": float(application["jarak_km"]),
            "waktu_tempuh_menit": int(application["waktu_tempuh_menit"]),
            "kelurahan": application["kelurahan"],
            "akses_jalan": application["akses_jalan"],
        }
        sample = pd.DataFrame(
            [{name: inspection_values.get(name) for name in model_features}],
            columns=model_features,
        )
        probabilities = model.predict_proba(sample)[0]
        distance = float(application["jarak_km"])
        predicted = classify_distance(distance)
        confidence = model_accuracy()
        if predicted == "Outsider Jauh":
            ml_status = "Layak sebagai Outsider Jauh"
            eligible = 1
        else:
            ml_status = "Tidak layak sebagai Outsider Jauh"
            eligible = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.execute(
            """UPDATE applications SET ml_prediction = ?, ml_confidence = ?, ml_status = ?,
               ml_eligible = ?, updated_at = ? WHERE id = ?""",
            (predicted, confidence, ml_status, eligible, now, application_id),
        )
        connection.execute(
            "INSERT INTO inspections ("
            "student_id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan, "
            "jarak_km, waktu_tempuh_menit, akses_jalan, kategori_terdaftar, "
            "prediksi_kategori, confidence_score, status, keterangan, tanggal_pemeriksaan"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                application["student_email"],
                application["nama_mahasiswa"],
                application["nama_kost"],
                application["alamat_kost"],
                application["kelurahan"],
                float(application["jarak_km"]),
                int(application["waktu_tempuh_menit"]),
                application["akses_jalan"],
                application["category"],
                predicted,
                confidence,
                "Sesuai Kategori" if predicted == application["category"] else "Berpotensi Tidak Sesuai",
                ml_status,
                now,
            ),
        )
        updated = connection.execute(
            """SELECT applications.*,
                (SELECT group_concat(document_type, ',')
                 FROM application_documents
                 WHERE application_id = applications.id) AS document_types
                FROM applications WHERE id = ?""",
            (application_id,),
        ).fetchone()
    return application_record(updated)


@app.patch("/api/applications/{application_id}")
def decide_application(
    application_id: int,
    payload: ApplicationDecision,
    user: dict = Depends(require_admin),
):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        application = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if application is None:
            raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan.")
        application = as_dict(application)
        if payload.status == "Disetujui":
            if not application["ml_prediction"]:
                raise HTTPException(
                    status_code=409,
                    detail="Analisis ML harus dijalankan sebelum pengajuan disetujui.",
                )
            if not application["ml_eligible"]:
                raise HTTPException(
                    status_code=409,
                    detail="Pengajuan belum layak sebagai Outsider Jauh menurut hasil ML.",
                )
        cursor = connection.execute(
            """UPDATE applications SET status = ?, admin_note = ?, updated_at = ?
            WHERE id = ?""",
            (payload.status, payload.admin_note.strip(), now, application_id),
        )
        if payload.status == "Disetujui" and application["ml_eligible"]:
            student_id = f"APP-{application_id:05d}"
            existing = connection.execute(
                "SELECT id FROM students WHERE id = ?", (student_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO students (
                        id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan,
                        jarak_km, kategori_terdaftar
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Outsider Jauh')""",
                    (
                        student_id,
                        application["nama_mahasiswa"],
                        application["nama_kost"],
                        application["alamat_kost"],
                        application["kelurahan"],
                        application["jarak_km"],
                    ),
                )
        connection.execute(
            "INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at) "
            "VALUES (?, ?, 'application', ?, ?)",
            (user["email"], f"application_{payload.status.lower().replace(' ', '_')}", str(application_id), now),
        )
        row = connection.execute(
            """SELECT applications.*,
                (SELECT group_concat(document_type, ',')
                 FROM application_documents
                 WHERE application_id = applications.id) AS document_types
                FROM applications WHERE id = ?""",
            (application_id,),
        ).fetchone()
    return application_record(row)


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
    sample = pd.DataFrame(
        [{name: getattr(payload, name) for name in model_features}],
        columns=model_features,
    )
    probabilities = model.predict_proba(sample)[0]
    best_index = int(probabilities.argmax())
    predicted = classify_distance(payload.jarak_km)
    confidence = model_accuracy()
    mismatch = payload.kategori_terdaftar != predicted
    if mismatch:
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
