import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from auth import (
    clear_session_cookie,
    current_user,
    hash_password,
    is_student_email,
    set_session_cookie,
    verify_google_credential,
    verify_password,
)
from schemas import GoogleCredential, StudentCreate


class VerifyGoogleCredentialTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-client-id",
                "ADMIN_EMAILS": "staff@example.unklab.ac.id",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.token_verification = patch(
            "auth.id_token.verify_oauth2_token",
            return_value={
                "email": "staff@example.unklab.ac.id",
                "email_verified": True,
                "name": "Staff Demo",
            },
        )
        self.token_verification.start()
        self.addCleanup(self.token_verification.stop)

    def test_admin_can_request_student_portal_role(self):
        user = verify_google_credential(
            "google-token", "staff@example.unklab.ac.id", "student"
        )

        self.assertEqual(user["role"], "student")

    def test_allowlisted_admin_can_request_admin_role(self):
        user = verify_google_credential(
            "google-token", "staff@example.unklab.ac.id", "admin"
        )

        self.assertEqual(user["role"], "admin")

    def test_email_must_match_verified_google_account(self):
        with self.assertRaises(HTTPException) as error:
            verify_google_credential(
                "google-token", "other@example.unklab.ac.id", "student"
            )

        self.assertEqual(error.exception.status_code, 403)

    def test_student_role_cannot_be_requested_for_non_student_email(self):
        with patch(
            "auth.id_token.verify_oauth2_token",
            return_value={
                "email": "person@example.com",
                "email_verified": True,
                "name": "Person",
            },
        ):
            with self.assertRaises(HTTPException) as error:
                verify_google_credential(
                    "google-token", "person@example.com", "student"
                )

        self.assertEqual(error.exception.status_code, 403)

    def test_student_role_requires_student_number_email_format(self):
        with patch(
            "auth.id_token.verify_oauth2_token",
            return_value={
                "email": "student@student.unklab.ac.id",
                "email_verified": True,
                "name": "Student",
            },
        ):
            with self.assertRaises(HTTPException) as error:
                verify_google_credential(
                    "google-token", "student@student.unklab.ac.id", "student"
                )

        self.assertEqual(error.exception.status_code, 403)

    def test_student_login_email_requires_eight_digit_id(self):
        self.assertTrue(is_student_email("12410292@student.unklab.ac.id"))
        self.assertTrue(is_student_email("s22210609@student.unklab.ac.id"))
        self.assertFalse(is_student_email("student@student.unklab.ac.id"))
        self.assertFalse(is_student_email("s123@student.unklab.ac.id"))
        self.assertFalse(is_student_email("s22210609@gmail.com"))

    def test_password_hash_verifies_only_the_original_password(self):
        encoded = hash_password("student-test-password")

        self.assertTrue(verify_password("student-test-password", encoded))
        self.assertFalse(verify_password("different-password", encoded))
        self.assertFalse(verify_password("student-test-password", "not-a-hash"))

    def test_student_cannot_request_admin_role(self):
        with patch(
            "auth.id_token.verify_oauth2_token",
            return_value={
                "email": "s22210609@student.unklab.ac.id",
                "email_verified": True,
                "name": "Student",
            },
        ):
            with self.assertRaises(HTTPException) as error:
                verify_google_credential(
                    "google-token", "s22210609@student.unklab.ac.id", "admin"
                )

        self.assertEqual(error.exception.status_code, 403)

    def test_email_input_is_normalized(self):
        credential = GoogleCredential(
            credential="x" * 20,
            email=" STAFF@example.unklab.ac.id ",
            requested_role="admin",
        )

        self.assertEqual(credential.email, "staff@example.unklab.ac.id")

    def test_house_residence_values_are_supported_and_trimmed(self):
        student = StudentCreate(
            id="VD-HOME-1",
            nama_mahasiswa="Mahasiswa Demo",
            nama_kost=" Rumah pribadi/keluarga ",
            alamat_kost=" Area rumah (tanpa alamat rinci) ",
            kelurahan="Airmadidi Bawah",
            jarak_km=1.0,
            kategori_terdaftar="Outsider Dekat",
        )

        self.assertEqual(student.nama_kost, "Rumah pribadi/keluarga")
        self.assertEqual(student.alamat_kost, "Area rumah (tanpa alamat rinci)")


class SessionCookieTests(unittest.TestCase):
    @staticmethod
    def request(host: str, cookie: str = "") -> Request:
        headers = [(b"host", f"{host}:8000".encode())]
        if cookie:
            headers.append((b"cookie", cookie.encode()))
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/auth/google",
                "raw_path": b"/api/auth/google",
                "query_string": b"",
                "headers": headers,
                "server": (host, 8000),
                "client": ("127.0.0.1", 1234),
            }
        )

    def test_local_session_cookie_round_trips_as_httponly_lax_cookie(self):
        user = {
            "email": "admin@example.com",
            "name": "Admin",
            "role": "admin",
        }
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ):
            response = Response()
            set_session_cookie(response, user, self.request("localhost"))
            cookie_header = response.headers["set-cookie"]
            cookie = cookie_header.split(";", 1)[0]

            self.assertIn("httponly", cookie_header.lower())
            self.assertIn("samesite=lax", cookie_header.lower())
            self.assertNotIn("secure", cookie_header.lower())
            self.assertEqual(
                current_user(self.request("localhost", cookie)),
                user,
            )

    def test_insecure_cookie_is_rejected_for_non_localhost(self):
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ):
            with self.assertRaises(HTTPException) as error:
                set_session_cookie(
                    Response(),
                    {"email": "admin@example.com", "name": "Admin", "role": "admin"},
                    self.request("example.com"),
                )

        self.assertEqual(error.exception.status_code, 503)

    def test_cookie_deletion_uses_matching_local_policy(self):
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ):
            response = Response()
            clear_session_cookie(response, self.request("127.0.0.1"))

        cookie_header = response.headers["set-cookie"].lower()
        self.assertIn("samesite=lax", cookie_header)
        self.assertIn("max-age=0", cookie_header)
        self.assertNotIn("secure", cookie_header)


if __name__ == "__main__":
    unittest.main()
