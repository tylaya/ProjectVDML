import json
import hashlib
import logging
import os
import secrets
import smtplib
import sqlite3
import subprocess
import sys
from email.message import EmailMessage
from io import BytesIO
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
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
    require_kost_owner,
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
from location_analysis import (
    haversine_km,
    is_in_north_sulawesi,
    parse_google_maps_coordinates,
)
from schemas import (
    ApplicationCreate,
    ApplicationDecision,
    GoogleCredential,
    InspectionInput,
    InspectionResult,
    KostApproval,
    KostCreate,
    KostConfirmation,
    KostLocationUpdate,
    PasswordReset,
    PasswordResetRequest,
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


def predict_category(sample: pd.DataFrame) -> tuple[str, float]:
    if model is None:
        raise RuntimeError("Model ML belum siap.")
    probabilities = model.predict_proba(sample)[0]
    predicted = str(model.predict(sample)[0])
    return predicted, float(max(probabilities))


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
        if user["role"] != "kost_owner":
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
        requested_role = payload.requested_role or "admin"
        if requested_role == "kost_owner":
            raise HTTPException(
                status_code=403,
                detail="Pemilik kost harus masuk menggunakan Google.",
            )
        admin_password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
        if not admin_password_hash or not is_valid_password_hash(admin_password_hash):
            raise HTTPException(
                status_code=503,
                detail="Kredensial admin belum dikonfigurasi dengan hash scrypt yang valid.",
            )
        if not verify_password(payload.password, admin_password_hash):
            raise HTTPException(status_code=401, detail="Email atau password tidak valid.")
        user = {"email": email, "name": "Admin Village Dean", "role": requested_role}
        record_login(user)
    else:
        if payload.requested_role == "admin":
            raise HTTPException(
                status_code=403,
                detail="Email ini tidak terdaftar sebagai staf/admin.",
            )
        if payload.requested_role == "kost_owner":
            raise HTTPException(
                status_code=403,
                detail="Pemilik kost harus masuk menggunakan Google.",
            )
        if not is_student_email(email):
            raise HTTPException(
                status_code=403,
                detail="Gunakan email mahasiswa berformat 12410292 atau s12410292@student.unklab.ac.id.",
            )
        with get_connection() as connection:
            row = connection.execute(
                "SELECT display_name, role, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if row is None:
                raise HTTPException(
                    status_code=401,
                    detail="Akun belum terdaftar. Buat akun terlebih dahulu dengan Google.",
                )
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
    verified_user = verify_google_credential(payload.credential, email, "student")
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
                    (verified_user["name"], password_hash, now, email),
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
                    (email, verified_user["name"], now, now, password_hash),
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
        "name": verified_user["name"],
        "role": "student",
    }
    set_session_cookie(response, user, request)
    return user


def send_password_reset_email(email: str, token: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    if not host or not sender:
        raise HTTPException(
            status_code=503,
            detail="Reset password belum dikonfigurasi. Atur SMTP_HOST dan SMTP_FROM di backend.",
        )
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        message = EmailMessage()
        message["Subject"] = "Atur ulang password SIGAP-VD"
        message["From"] = sender
        message["To"] = email
        reset_url = (
            os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
            + "/?reset_token="
            + token
        )
        message.set_content(
            "Gunakan tautan berikut untuk mengatur ulang password Anda. "
            "Tautan berlaku selama satu jam dan hanya dapat digunakan sekali:\n\n"
            f"{reset_url}\n\nJika Anda tidak meminta reset, abaikan email ini."
        )
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if os.environ.get("SMTP_STARTTLS", "true").strip().lower() == "true":
                smtp.starttls()
            username = os.environ.get("SMTP_USERNAME", "").strip()
            if username:
                smtp.login(username, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)
    except (OSError, ValueError, smtplib.SMTPException) as error:
        logger.exception("Email reset password gagal dikirim.")
        raise HTTPException(
            status_code=503,
            detail="Email reset password gagal dikirim. Periksa konfigurasi SMTP.",
        ) from error


@app.post("/api/auth/password-reset/request")
def request_password_reset(payload: PasswordResetRequest):
    if not is_student_email(payload.email):
        raise HTTPException(
            status_code=422,
            detail="Reset password hanya tersedia untuk email mahasiswa terdaftar.",
        )
    with get_connection() as connection:
        account = connection.execute(
            "SELECT email FROM users WHERE email = ? AND role = 'student'",
            (payload.email,),
        ).fetchone()
        if account is None:
            return {"message": "Jika akun terdaftar, tautan reset akan dikirim ke email."}
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(
            timespec="seconds"
        )
        connection.execute(
            """INSERT INTO password_reset_tokens (email, token_hash, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                token_hash = excluded.token_hash, expires_at = excluded.expires_at""",
            (
                payload.email,
                hashlib.sha256(token.encode("utf-8")).hexdigest(),
                expires_at,
            ),
        )
    send_password_reset_email(payload.email, token)
    return {"message": "Jika akun terdaftar, tautan reset akan dikirim ke email."}


@app.post("/api/auth/password-reset")
def reset_password(payload: PasswordReset):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        token_record = connection.execute(
            """SELECT email FROM password_reset_tokens
               WHERE token_hash = ? AND expires_at > ?""",
            (token_hash, now),
        ).fetchone()
        if token_record is None:
            raise HTTPException(
                status_code=400,
                detail="Tautan reset tidak valid atau telah kedaluwarsa.",
            )
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE email = ? AND role = 'student'",
            (hash_password(payload.password), token_record["email"]),
        )
        connection.execute(
            "DELETE FROM password_reset_tokens WHERE email = ?",
            (token_record["email"],),
        )
        connection.execute(
            """INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at)
               VALUES (?, 'password_reset', 'user', ?, ?)""",
            (token_record["email"], token_record["email"], now),
        )
    return {"message": "Password berhasil diperbarui. Silakan masuk."}


@app.get("/api/auth/me")
def read_current_user(user: dict = Depends(current_user)):
    return user


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user: dict = Depends(current_user)):
    clear_session_cookie(response, request)
    return {"message": f"Sesi {user['email']} telah berakhir."}


@app.get("/api/kosts/approved")
def list_approved_kosts(_user: dict = Depends(require_student)):
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT id, name, address, kelurahan, residence_type, maps_url
               FROM kosts
               WHERE approval_status = 'Disetujui' AND location_anomaly = 0
                 AND maps_url != ''
               ORDER BY name"""
        ).fetchall()
    return [as_dict(row) for row in rows]


@app.get("/api/kosts")
def list_kosts(_user: dict = Depends(require_admin)):
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM kosts ORDER BY id DESC").fetchall()
    return [as_dict(row) for row in rows]


@app.post("/api/kosts", status_code=201)
def create_kost(payload: KostCreate, user: dict = Depends(require_admin)):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    latitude, longitude = parse_google_maps_coordinates(payload.maps_url)
    location_anomaly = not is_in_north_sulawesi(latitude, longitude)
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """INSERT INTO kosts (
                    name, address, kelurahan, residence_type, owner_email,
                    approval_status, created_at, updated_at, maps_url, location_anomaly
                ) VALUES (?, ?, ?, ?, ?, 'Menunggu approval', ?, ?, ?, ?)""",
                (
                    payload.name,
                    payload.address,
                    payload.kelurahan,
                    payload.residence_type,
                    payload.owner_email,
                    now,
                    now,
                    payload.maps_url,
                    location_anomaly,
                ),
            )
            kost = connection.execute(
                "SELECT * FROM kosts WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.execute(
                """INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at)
                   VALUES (?, 'kost_submitted_for_approval', 'kost', ?, ?)""",
                (user["email"], str(cursor.lastrowid), now),
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: kosts.name, kosts.address" in str(error):
            raise HTTPException(
                status_code=409, detail="Kost dengan nama dan alamat tersebut sudah terdaftar."
            ) from error
        raise
    return as_dict(kost)


@app.patch("/api/kosts/{kost_id}/location")
def update_kost_location(
    kost_id: int,
    payload: KostLocationUpdate,
    user: dict = Depends(require_admin),
):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            """UPDATE kosts SET maps_url = ?, location_anomaly = ?,
               approval_status = 'Menunggu approval', updated_at = ? WHERE id = ?""",
            (
                payload.maps_url,
                not is_in_north_sulawesi(
                    *parse_google_maps_coordinates(payload.maps_url)
                ),
                now,
                kost_id,
            ),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data kost tidak ditemukan.")
        connection.execute(
            """INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at)
               VALUES (?, 'kost_location_updated', 'kost', ?, ?)""",
            (user["email"], str(kost_id), now),
        )
        row = connection.execute("SELECT * FROM kosts WHERE id = ?", (kost_id,)).fetchone()
    return as_dict(row)


@app.patch("/api/kosts/{kost_id}/approval")
def decide_kost(
    kost_id: int,
    payload: KostApproval,
    user: dict = Depends(require_admin),
):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        kost = connection.execute(
            "SELECT location_anomaly, maps_url FROM kosts WHERE id = ?", (kost_id,)
        ).fetchone()
        if kost is None:
            raise HTTPException(status_code=404, detail="Data kost tidak ditemukan.")
        if payload.approval_status == "Disetujui" and kost["location_anomaly"]:
            raise HTTPException(
                status_code=409,
                detail="Kost di luar Sulawesi Utara ditandai sebagai anomali dan tidak dapat disetujui.",
            )
        if payload.approval_status == "Disetujui" and not kost["maps_url"]:
            raise HTTPException(
                status_code=409,
                detail="Tautan lokasi Google Maps harus diisi sebelum kost dapat disetujui.",
            )
        cursor = connection.execute(
            "UPDATE kosts SET approval_status = ?, updated_at = ? WHERE id = ?",
            (payload.approval_status, now, kost_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data kost tidak ditemukan.")
        connection.execute(
            """INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at)
               VALUES (?, ?, 'kost', ?, ?)""",
            (
                user["email"],
                f"kost_{payload.approval_status.lower()}",
                str(kost_id),
                now,
            ),
        )
        row = connection.execute("SELECT * FROM kosts WHERE id = ?", (kost_id,)).fetchone()
    return as_dict(row)


@app.get("/api/owner/applications")
def owner_applications(user: dict = Depends(require_kost_owner)):
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT applications.* FROM applications
               JOIN kosts ON kosts.id = applications.kost_id
               WHERE kosts.owner_email = ? AND kosts.approval_status = 'Disetujui'
                 AND kosts.location_anomaly = 0 AND kosts.maps_url != ''
               ORDER BY applications.id DESC""",
            (user["email"],),
        ).fetchall()
    return [application_record(row) for row in rows]


@app.patch("/api/owner/applications/{application_id}/confirmation")
def confirm_kost_occupant(
    application_id: int,
    payload: KostConfirmation,
    user: dict = Depends(require_kost_owner),
):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        application = connection.execute(
            """SELECT applications.id FROM applications
               JOIN kosts ON kosts.id = applications.kost_id
               WHERE applications.id = ? AND kosts.owner_email = ?
                 AND kosts.approval_status = 'Disetujui'
                 AND kosts.location_anomaly = 0 AND kosts.maps_url != ''
                 AND applications.residence_type = kosts.residence_type""",
            (application_id, user["email"]),
        ).fetchone()
        if application is None:
            raise HTTPException(status_code=404, detail="Pengajuan kost tidak ditemukan.")
        connection.execute(
            """UPDATE applications SET kost_confirmation_status = ?,
               kost_confirmation_note = ?, updated_at = ? WHERE id = ?""",
            (payload.status, payload.note.strip(), now, application_id),
        )
        connection.execute(
            """INSERT INTO audit_logs (actor_email, action, object_type, object_id, occurred_at)
               VALUES (?, ?, 'application', ?, ?)""",
            (
                user["email"],
                f"kost_occupancy_{payload.status.lower()}",
                str(application_id),
                now,
            ),
        )
        row = connection.execute(
            """SELECT applications.*,
                (SELECT group_concat(document_type, ',') FROM application_documents
                 WHERE application_id = applications.id) AS document_types
                FROM applications WHERE id = ?""",
            (application_id,),
        ).fetchone()
    return application_record(row)


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


def registration_period(settings: dict, today: date | None = None):
    semester_name = settings["semester_name"]
    start_date = settings["semester_start_date"]
    if not semester_name or not start_date:
        return {
            "configured": False,
            "location_configured": bool(settings.get("campus_maps_url")),
            "semester_name": semester_name,
            "start_date": None,
            "end_date": None,
            "is_open": False,
        }

    start = date.fromisoformat(start_date)
    end = start + timedelta(days=4)
    current_date = today or datetime.now(timezone(timedelta(hours=8))).date()
    return {
        "configured": True,
        "location_configured": bool(settings.get("campus_maps_url")),
        "semester_name": semester_name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "is_open": start <= current_date <= end,
    }


def location_assessment(maps_url: str, campus_maps_url: str):
    if not maps_url:
        raise HTTPException(
            status_code=422,
            detail="Tautan lokasi Google Maps wajib diisi.",
        )
    if not campus_maps_url:
        raise HTTPException(
            status_code=503,
            detail="Lokasi kampus belum dikonfigurasi admin Village Dean.",
        )
    try:
        latitude, longitude = parse_google_maps_coordinates(maps_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        campus_coordinates = parse_google_maps_coordinates(campus_maps_url)
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="Tautan lokasi kampus tidak valid. Periksa Pengaturan Sistem.",
        ) from error
    return {
        "latitude": latitude,
        "longitude": longitude,
        "jarak_km": haversine_km(campus_coordinates, (latitude, longitude)),
        "inside_north_sulawesi": is_in_north_sulawesi(latitude, longitude),
    }


def recommend_application(
    application: dict,
    location: dict,
    document_types: set[str],
    settings: dict,
):
    if model is None:
        return "", 0.0, "Model ML belum siap; perlu tinjauan manual.", 0

    sample = pd.DataFrame(
        [
            {
                "jarak_km": float(application["jarak_km"]),
                "waktu_tempuh_menit": int(application["waktu_tempuh_menit"]),
                "kelurahan": application["kelurahan"],
                "akses_jalan": application["akses_jalan"],
            }
        ],
        columns=model_features,
    )
    predicted, confidence = predict_category(sample)
    required_documents = {"surat_penerimaan_kost" if application["residence_type"] in {"Kost putra", "Kost putri"} else "surat_domisili"}
    if (
        application["category"] == "Outsider Jauh"
        or application["residence_type"] in {"Keluarga", "Wali"}
    ):
        required_documents.update({"ktp", "kartu_keluarga"})
    documents_complete = required_documents.issubset(document_types)

    if not location["inside_north_sulawesi"]:
        status = "Anomali lokasi: di luar Sulawesi Utara; perlu ditinjau petugas."
    elif not documents_complete:
        status = "Dokumen belum lengkap; perlu ditinjau petugas."
    elif predicted != application["category"]:
        status = f"Prediksi {predicted} berbeda dari kategori yang dipilih; perlu ditinjau petugas."
    elif confidence < settings["confidence_threshold"]:
        status = "Confidence model di bawah ambang; perlu ditinjau petugas."
    elif predicted == "Outsider Jauh":
        status = "Dokumen lengkap dan lokasi sesuai; rekomendasi Outsider Jauh untuk dipertimbangkan petugas."
    else:
        status = "Rekomendasi Outsider Dekat; perlu ditinjau sesuai kebijakan Village Dean."

    eligible = int(
        location["inside_north_sulawesi"]
        and documents_complete
        and predicted == application["category"] == "Outsider Jauh"
        and confidence >= settings["confidence_threshold"]
    )
    return predicted, confidence, status, eligible


def resolve_application_residence(connection, payload: ApplicationCreate) -> ApplicationCreate:
    kost_types = {"Kost putra", "Kost putri"}
    if payload.residence_type in kost_types:
        if payload.kost_id is None:
            raise HTTPException(
                status_code=422,
                detail="Pilih kost yang telah disetujui kampus.",
            )
        kost = connection.execute(
            """SELECT id, name, address, kelurahan, residence_type, maps_url
               FROM kosts
               WHERE id = ? AND approval_status = 'Disetujui'
                 AND location_anomaly = 0 AND maps_url != ''""",
            (payload.kost_id,),
        ).fetchone()
        if kost is None:
            raise HTTPException(
                status_code=422,
                detail="Kost tidak ditemukan atau belum disetujui kampus.",
            )
        if kost["residence_type"] != payload.residence_type:
            raise HTTPException(
                status_code=422,
                detail="Jenis kost tidak sesuai dengan pilihan mahasiswa.",
            )
        return payload.model_copy(
            update={
                "nama_kost": kost["name"],
                "alamat_kost": kost["address"],
                "kelurahan": kost["kelurahan"],
                "maps_url": kost["maps_url"],
            }
        )
    if payload.kost_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Hunian rumah tidak dapat menggunakan ID kost.",
        )
    return payload


def insert_application(connection, payload: ApplicationCreate, user: dict, now: str):
    is_kost = payload.residence_type in {"Kost putra", "Kost putri"}
    cursor = connection.execute(
        """INSERT INTO applications (
            student_email, request_type, category, residence_type, kost_id,
            kost_confirmation_status, semester,
            nama_mahasiswa, nama_kost, alamat_kost, maps_url, kelurahan, jarak_km,
            waktu_tempuh_menit, akses_jalan, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user["email"],
            payload.request_type,
            payload.category,
            payload.residence_type,
            payload.kost_id,
            "Menunggu kost" if is_kost else "Tidak diperlukan",
            payload.semester.strip(),
            payload.nama_mahasiswa.strip(),
            payload.nama_kost.strip(),
            payload.alamat_kost.strip(),
            payload.maps_url or "",
            payload.kelurahan.strip(),
            payload.jarak_km if payload.jarak_km is not None else 0,
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
def create_application(_user: dict = Depends(require_student)):
    raise HTTPException(
        status_code=422,
        detail="Pengajuan wajib menyertakan surat bukti hunian. Gunakan formulir dengan unggahan dokumen.",
    )


async def read_upload(document_type: str, upload: UploadFile | None):
    if upload is None:
        raise HTTPException(
            status_code=422,
            detail=f"Berkas {DOCUMENT_TYPES[document_type]} wajib diunggah.",
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
    surat_penerimaan_kost: UploadFile | None = File(default=None),
    surat_domisili: UploadFile | None = File(default=None),
    user: dict = Depends(require_student),
):
    try:
        application_payload = ApplicationCreate.model_validate_json(payload)
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=json.loads(error.json()),
        ) from error

    settings = get_settings()
    period = registration_period(settings)
    if not period["is_open"]:
        if period["configured"]:
            detail = (
                f"Pendaftaran {period['semester_name']} hanya dibuka "
                f"{period['start_date']} sampai {period['end_date']}."
            )
        else:
            detail = "Jadwal semester belum dikonfigurasi oleh admin Village Dean."
        raise HTTPException(status_code=403, detail=detail)

    with get_connection() as connection:
        application_payload = resolve_application_residence(connection, application_payload)
    location = location_assessment(
        application_payload.maps_url or "", settings["campus_maps_url"]
    )
    application_payload = application_payload.model_copy(
        update={"jarak_km": location["jarak_km"]}
    )

    residence_document = (
        "surat_penerimaan_kost"
        if application_payload.residence_type in {"Kost putra", "Kost putri"}
        else "surat_domisili"
    )
    expected_uploads = {
        residence_document: (
            surat_penerimaan_kost if residence_document == "surat_penerimaan_kost" else surat_domisili
        )
    }
    requires_identity_documents = (
        application_payload.category == "Outsider Jauh"
        or application_payload.residence_type in {"Keluarga", "Wali"}
    )
    if requires_identity_documents:
        expected_uploads.update({"ktp": ktp, "kartu_keluarga": kartu_keluarga})
    elif ktp is not None or kartu_keluarga is not None:
        raise HTTPException(
            status_code=422,
            detail="Berkas KTP dan Kartu Keluarga tidak diperlukan untuk Outsider Dekat yang tinggal di kost.",
        )
    if (
        application_payload.residence_type in {"Kost putra", "Kost putri"}
        and surat_domisili is not None
    ) or (
        application_payload.residence_type in {"Keluarga", "Wali"}
        and surat_penerimaan_kost is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="Unggah hanya dokumen hunian yang sesuai dengan tipe tempat tinggal.",
        )
    documents = {}
    for document_type, upload in expected_uploads.items():
        data, content_type = await read_upload(document_type, upload)
        documents[document_type] = (data, content_type)

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
            application_row = connection.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
            prediction, confidence, ml_status, eligible = recommend_application(
                as_dict(application_row),
                location,
                set(documents),
                settings,
            )
            connection.execute(
                """UPDATE applications SET ml_prediction = ?, ml_confidence = ?,
                   ml_status = ?, ml_eligible = ?, updated_at = ? WHERE id = ?""",
                (
                    prediction,
                    confidence,
                    ml_status,
                    eligible,
                    now,
                    application_id,
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
    query += (
        " ORDER BY CASE status WHEN 'Menunggu verifikasi' THEN 0 ELSE 1 END, "
        "CASE WHEN ml_eligible = 1 THEN 0 ELSE 1 END, id DESC"
    )
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
    settings = get_settings()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan.")
        application = as_dict(row)
        if not application["nama_mahasiswa"] or application["jarak_km"] is None:
            raise HTTPException(
                status_code=422,
                detail="Pengajuan lama belum memiliki data hunian dan jarak untuk dianalisis.",
            )
        location = location_assessment(
            application["maps_url"], settings["campus_maps_url"]
        )
        application["jarak_km"] = location["jarak_km"]
        document_rows = connection.execute(
            "SELECT document_type FROM application_documents WHERE application_id = ?",
            (application_id,),
        ).fetchall()
        prediction, confidence, ml_status, eligible = recommend_application(
            application,
            location,
            {document["document_type"] for document in document_rows},
            settings,
        )
        if not prediction:
            raise HTTPException(status_code=503, detail=ml_status)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.execute(
            """UPDATE applications SET jarak_km = ?, ml_prediction = ?, ml_confidence = ?,
               ml_status = ?, ml_eligible = ?, updated_at = ? WHERE id = ?""",
            (
                location["jarak_km"],
                prediction,
                confidence,
                ml_status,
                eligible,
                now,
                application_id,
            ),
        )
        inspection_status = (
            "Berpotensi Tidak Sesuai"
            if not location["inside_north_sulawesi"]
            or prediction != application["category"]
            else "Sesuai Kategori"
        )
        connection.execute(
            "INSERT INTO inspections ("
            "student_id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan, "
            "jarak_km, waktu_tempuh_menit, akses_jalan, kategori_terdaftar, "
            "prediksi_kategori, confidence_score, status, keterangan, tanggal_pemeriksaan, maps_url"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                prediction,
                confidence,
                inspection_status,
                ml_status,
                now,
                application["maps_url"],
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
            if application["residence_type"] in {"Kost putra", "Kost putri"}:
                kost = connection.execute(
                    "SELECT approval_status, location_anomaly, maps_url FROM kosts WHERE id = ?",
                    (application["kost_id"],),
                ).fetchone()
                if (
                    kost is None
                    or kost["approval_status"] != "Disetujui"
                    or kost["location_anomaly"]
                    or not kost["maps_url"]
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Kost harus tetap berstatus Disetujui sebelum pengajuan dapat disetujui.",
                    )
                if application["kost_confirmation_status"] != "Dikonfirmasi":
                    raise HTTPException(
                        status_code=409,
                        detail="Pemilik kost harus mengonfirmasi status penghuni sebelum pengajuan disetujui.",
                    )
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
            connection.execute(
                """INSERT INTO students (
                    id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan,
                    jarak_km, kategori_terdaftar, maps_url, location_anomaly
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET
                    nama_mahasiswa = excluded.nama_mahasiswa,
                    nama_kost = excluded.nama_kost,
                    alamat_kost = excluded.alamat_kost,
                    kelurahan = excluded.kelurahan,
                    jarak_km = excluded.jarak_km,
                    kategori_terdaftar = excluded.kategori_terdaftar,
                    maps_url = excluded.maps_url,
                    location_anomaly = excluded.location_anomaly""",
                (
                    student_id,
                    application["nama_mahasiswa"],
                    application["nama_kost"],
                    application["alamat_kost"],
                    application["kelurahan"],
                    application["jarak_km"],
                    application["ml_prediction"],
                    application["maps_url"],
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
    if not student.maps_url:
        raise HTTPException(status_code=422, detail="Tautan Google Maps lokasi wajib diisi.")
    location = location_assessment(student.maps_url, get_settings()["campus_maps_url"])
    values = student.model_dump()
    values["jarak_km"] = location["jarak_km"]
    values["location_anomaly"] = not location["inside_north_sulawesi"]
    try:
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO students
                (id, nama_mahasiswa, nama_kost, alamat_kost, kelurahan, jarak_km, kategori_terdaftar, maps_url, location_anomaly)
                VALUES (:id, :nama_mahasiswa, :nama_kost, :alamat_kost, :kelurahan, :jarak_km, :kategori_terdaftar, :maps_url, :location_anomaly)""",
                values,
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(status_code=409, detail="ID mahasiswa tersebut sudah digunakan.") from error
        raise
    return values


@app.put("/api/students/{student_id}", response_model=Student)
def update_student(student_id: str, student: StudentUpdate, _user: dict = Depends(require_admin)):
    if not student.maps_url:
        raise HTTPException(status_code=422, detail="Tautan Google Maps lokasi wajib diisi.")
    location = location_assessment(student.maps_url, get_settings()["campus_maps_url"])
    values = student.model_dump()
    values["jarak_km"] = location["jarak_km"]
    values["location_anomaly"] = not location["inside_north_sulawesi"]
    with get_connection() as connection:
        cursor = connection.execute(
            """UPDATE students SET nama_mahasiswa=:nama_mahasiswa, nama_kost=:nama_kost,
            alamat_kost=:alamat_kost, kelurahan=:kelurahan, jarak_km=:jarak_km,
            kategori_terdaftar=:kategori_terdaftar, maps_url=:maps_url,
            location_anomaly=:location_anomaly WHERE id=:id""",
            {**values, "id": student_id},
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data mahasiswa tidak ditemukan.")
    return {"id": student_id, **values}


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
    if not payload.maps_url:
        raise HTTPException(
            status_code=422,
            detail="Tautan Google Maps lokasi wajib diisi agar jarak dan batas provinsi dapat diverifikasi.",
        )
    location = None
    if payload.maps_url:
        location = location_assessment(
            payload.maps_url, get_settings()["campus_maps_url"]
        )
        payload = payload.model_copy(update={"jarak_km": location["jarak_km"]})
    sample = pd.DataFrame(
        [{name: getattr(payload, name) for name in model_features}],
        columns=model_features,
    )
    predicted, confidence = predict_category(sample)
    outside_region = location is not None and not location["inside_north_sulawesi"]
    mismatch = payload.kategori_terdaftar != predicted or outside_region
    if mismatch:
        status = "Berpotensi Tidak Sesuai"
        if outside_region:
            explanation = (
                "Koordinat lokasi berada di luar batas Sulawesi Utara; "
                "data ditandai sebagai anomali dan perlu verifikasi petugas."
            )
        else:
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
                prediksi_kategori, confidence_score, status, keterangan, tanggal_pemeriksaan,
                maps_url
            ) VALUES (
                :student_id, :nama_mahasiswa, :nama_kost, :alamat_kost, :kelurahan,
                :jarak_km, :waktu_tempuh_menit, :akses_jalan, :kategori_terdaftar,
                :prediksi_kategori, :confidence_score, :status, :keterangan, :tanggal_pemeriksaan,
                :maps_url
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
    return save_settings(settings.model_dump(mode="json"))


@app.get("/api/registration-period")
def read_registration_period(_user: dict = Depends(require_student)):
    return registration_period(get_settings())


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
