import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token


SESSION_COOKIE = "sigap_session"
SESSION_SECONDS = 8 * 60 * 60
PASSWORD_SCRYPT_N = 2**14
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1
PASSWORD_HASH_BYTES = 64


def is_student_email(email: str) -> bool:
    return bool(re.fullmatch(r"s?\d{8}@student\.unklab\.ac\.id", email.strip().lower()))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_HASH_BYTES,
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def _password_hash_parts(password_hash: str) -> tuple[bytes, bytes] | None:
    try:
        algorithm, salt_hex, digest_hex = password_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        digest = bytes.fromhex(digest_hex)
    except (AttributeError, ValueError):
        return None
    if algorithm != "scrypt" or len(salt) != 16 or len(digest) != PASSWORD_HASH_BYTES:
        return None
    return salt, digest


def is_valid_password_hash(password_hash: str) -> bool:
    return _password_hash_parts(password_hash) is not None


def verify_password(password: str, password_hash: str) -> bool:
    parts = _password_hash_parts(password_hash)
    if parts is None:
        return False
    salt, expected_digest = parts
    actual_digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_HASH_BYTES,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def _session_secret() -> str:
    secret = os.environ.get("SESSION_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Autentikasi belum dikonfigurasi: SESSION_SECRET minimal 32 karakter.",
        )
    return secret


def ensure_session_configuration() -> None:
    _session_secret()


def _cookie_options(request: Request) -> tuple[bool, str]:
    hostname = (request.url.hostname or "").lower()
    is_localhost = hostname in {"localhost", "127.0.0.1", "::1"}
    configured_secure = os.environ.get("COOKIE_SECURE", "").strip().lower()
    if configured_secure not in {"", "true", "false"}:
        raise HTTPException(
            status_code=503,
            detail="Konfigurasi COOKIE_SECURE harus bernilai true atau false.",
        )
    secure = configured_secure == "true" if configured_secure else not is_localhost
    if not is_localhost and not secure:
        raise HTTPException(
            status_code=503,
            detail="COOKIE_SECURE harus true untuk host selain localhost.",
        )

    same_site = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
    if same_site not in {"lax", "strict", "none"}:
        raise HTTPException(
            status_code=503,
            detail="COOKIE_SAMESITE harus bernilai lax, strict, atau none.",
        )
    if same_site == "none" and not secure:
        raise HTTPException(
            status_code=503,
            detail="COOKIE_SAMESITE=none memerlukan COOKIE_SECURE=true.",
        )
    return secure, same_site


def _admin_emails() -> set[str]:
    return {
        email.strip().lower()
        for email in os.environ.get("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def verify_google_credential(
    credential: str, expected_email: str, requested_role: str
) -> dict[str, str]:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="Autentikasi belum dikonfigurasi: GOOGLE_CLIENT_ID belum diatur.",
        )
    try:
        claims = id_token.verify_oauth2_token(credential, GoogleRequest(), client_id)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="Token Google tidak valid atau kedaluwarsa.") from error

    email = str(claims.get("email", "")).strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=403, detail="Email Google belum terverifikasi.")
    if email != expected_email.strip().lower():
        raise HTTPException(
            status_code=403,
            detail="Email Google yang dipilih harus sama dengan email yang dimasukkan.",
        )
    is_admin = email in _admin_emails()
    if requested_role == "admin" and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Email ini tidak terdaftar sebagai staf/admin.",
        )
    if requested_role == "student" and not is_admin and not is_student_email(email):
        raise HTTPException(
            status_code=403,
            detail="Gunakan email mahasiswa berformat 12345678 atau s12345678@student.unklab.ac.id.",
        )
    if requested_role == "kost_owner":
        from database import get_connection

        with get_connection() as connection:
            owner = connection.execute(
                """SELECT 1 FROM kosts
                   WHERE owner_email = ? AND approval_status = 'Disetujui' LIMIT 1""",
                (email,),
            ).fetchone()
        if owner is None:
            raise HTTPException(
                status_code=403,
                detail="Email ini belum terdaftar sebagai pemilik kost yang disetujui kampus.",
            )
    return {
        "email": email,
        "name": str(claims.get("name", email)),
        "role": requested_role,
    }


def set_session_cookie(
    response: Response, user: dict[str, str], request: Request
) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user["email"],
            "name": user["name"],
            "role": user["role"],
            "iat": now,
            "exp": now + timedelta(seconds=SESSION_SECONDS),
        },
        _session_secret(),
        algorithm="HS256",
    )
    secure, same_site = _cookie_options(request)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    secure, same_site = _cookie_options(request)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=secure,
        samesite=same_site,
    )


def current_user(request: Request) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Silakan masuk terlebih dahulu.")
    try:
        claims: dict[str, Any] = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Sesi tidak valid atau telah kedaluwarsa.") from error
    email = claims.get("sub")
    name = claims.get("name")
    role = claims.get("role")
    if (
        not isinstance(email, str)
        or not email
        or not isinstance(name, str)
        or not isinstance(role, str)
        or role not in {"admin", "student", "kost_owner"}
    ):
        raise HTTPException(status_code=401, detail="Sesi tidak valid atau telah kedaluwarsa.")
    return {
        "email": email,
        "name": name,
        "role": role,
    }


def require_admin(request: Request) -> dict[str, str]:
    user = current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses hanya tersedia untuk staf Village Dean.")
    return user


def require_student(request: Request) -> dict[str, str]:
    user = current_user(request)
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Fitur ini hanya tersedia untuk mahasiswa.")
    return user


def require_kost_owner(request: Request) -> dict[str, str]:
    user = current_user(request)
    if user["role"] != "kost_owner":
        raise HTTPException(status_code=403, detail="Fitur ini hanya tersedia untuk pemilik kost.")
    return user
