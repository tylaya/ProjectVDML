import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token


SESSION_COOKIE = "sigap_session"
SESSION_SECONDS = 8 * 60 * 60


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
    if requested_role == "student" and not is_admin and not email.endswith(
        "@student.unklab.ac.id"
    ):
        raise HTTPException(
            status_code=403,
            detail="Gunakan akun Google mahasiswa dengan domain @student.unklab.ac.id.",
        )
    return {
        "email": email,
        "name": str(claims.get("name", email)),
        "role": requested_role,
    }


def set_session_cookie(response: Response, user: dict[str, str]) -> None:
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
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")


def current_user(request: Request) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Silakan masuk terlebih dahulu.")
    try:
        claims: dict[str, Any] = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Sesi tidak valid atau telah kedaluwarsa.") from error
    return {
        "email": str(claims["sub"]),
        "name": str(claims["name"]),
        "role": str(claims["role"]),
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
