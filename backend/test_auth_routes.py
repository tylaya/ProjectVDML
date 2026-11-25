import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
import pandas as pd
from starlette.requests import Request
from starlette.responses import Response

import main
from auth import current_user, hash_password
from schemas import GoogleCredential, PasswordLogin, StudentRegistration


class ModelClassificationTests(unittest.TestCase):
    def test_analysis_uses_model_prediction_and_sample_confidence(self):
        classifier = MagicMock()
        classifier.predict.return_value = ["Outsider Dekat"]
        classifier.predict_proba.return_value = [[0.83, 0.17]]
        sample = pd.DataFrame([{"jarak_km": 4.0}])

        with patch.object(main, "model", classifier):
            prediction, confidence = main.predict_category(sample)

        self.assertEqual(prediction, "Outsider Dekat")
        self.assertEqual(confidence, 0.83)


class AuthRouteSessionTests(unittest.TestCase):
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

    def test_google_login_sets_cookie_used_by_me_for_each_role(self):
        test_cases = (
            ("adminvd@unklab.ac.id", "admin"),
            ("12410292@student.unklab.ac.id", "student"),
            ("s22210609@student.unklab.ac.id", "student"),
        )
        for email, role in test_cases:
            with self.subTest(role=role), patch.dict(
                os.environ,
                {
                    "SESSION_SECRET": "s" * 48,
                    "GOOGLE_CLIENT_ID": "test-client-id",
                    "ADMIN_EMAILS": "adminvd@unklab.ac.id",
                    "COOKIE_SECURE": "false",
                    "COOKIE_SAMESITE": "lax",
                },
                clear=True,
            ):
                user = {"email": email, "name": "Test User", "role": role}
                connection_context = MagicMock()
                connection_context.__enter__.return_value = MagicMock()
                with (
                    patch("main.verify_google_credential", return_value=user),
                    patch("main.get_connection", return_value=connection_context),
                ):
                    response = Response()
                    result = main.login_with_google(
                        GoogleCredential(
                            credential="x" * 20,
                            email=email,
                            requested_role=role,
                        ),
                        self.request("localhost"),
                        response,
                    )

                    cookie = response.headers["set-cookie"].lower()
                    self.assertIn("httponly", cookie)
                    self.assertIn("samesite=lax", cookie)
                    self.assertNotIn("secure", cookie)
                    cookie_value = response.headers["set-cookie"].split(";", 1)[0]
                    profile = main.read_current_user(
                        current_user(self.request("localhost", cookie_value))
                    )
                    self.assertEqual(result, user)
                    self.assertEqual(profile, user)

    def test_password_login_uses_admin_hash_and_sets_admin_session(self):
        admin_hash = hash_password("test-admin-password")
        connection_context = MagicMock()
        connection_context.__enter__.return_value = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "ADMIN_EMAILS": "adminVD@unklab.ac.id",
                "ADMIN_PASSWORD_HASH": admin_hash,
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ), patch("main.get_connection", return_value=connection_context):
            response = Response()
            user = main.login_with_password(
                PasswordLogin(
                    email="ADMINVD@unklab.ac.id",
                    password="test-admin-password",
                ),
                self.request("localhost"),
                response,
            )
            cookie_value = response.headers["set-cookie"].split(";", 1)[0]
            profile = main.read_current_user(
                current_user(self.request("localhost", cookie_value))
            )

        self.assertEqual(user["role"], "admin")
        self.assertEqual(profile["email"], "adminvd@unklab.ac.id")

    def test_admin_can_choose_student_role_during_password_login(self):
        admin_hash = hash_password("test-admin-password")
        connection_context = MagicMock()
        connection_context.__enter__.return_value = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "ADMIN_EMAILS": "adminVD@unklab.ac.id",
                "ADMIN_PASSWORD_HASH": admin_hash,
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ), patch("main.get_connection", return_value=connection_context):
            response = Response()
            user = main.login_with_password(
                PasswordLogin(
                    email="ADMINVD@unklab.ac.id",
                    password="test-admin-password",
                    requested_role="student",
                ),
                self.request("localhost"),
                response,
            )
            cookie_value = response.headers["set-cookie"].split(";", 1)[0]
            profile = main.read_current_user(
                current_user(self.request("localhost", cookie_value))
            )

        self.assertEqual(user["role"], "student")
        self.assertEqual(profile["role"], "student")

    def test_student_cannot_choose_admin_role_during_password_login(self):
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "ADMIN_EMAILS": "adminVD@unklab.ac.id",
            },
            clear=True,
        ):
            with self.assertRaises(HTTPException) as error:
                main.login_with_password(
                    PasswordLogin(
                        email="s22210609@student.unklab.ac.id",
                        password="student-password",
                        requested_role="admin",
                    ),
                    self.request("localhost"),
                    Response(),
                )

        self.assertEqual(error.exception.status_code, 403)

    def test_password_login_rejects_wrong_admin_password(self):
        admin_hash = hash_password("test-admin-password")
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "ADMIN_EMAILS": "adminVD@unklab.ac.id",
                "ADMIN_PASSWORD_HASH": admin_hash,
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ):
            with self.assertRaises(HTTPException) as error:
                main.login_with_password(
                    PasswordLogin(
                        email="adminVD@unklab.ac.id",
                        password="wrong-password",
                    ),
                    self.request("localhost"),
                    Response(),
                )

        self.assertEqual(error.exception.status_code, 401)

    def test_password_login_rejects_non_student_email(self):
        with patch.dict(
            os.environ,
            {"SESSION_SECRET": "s" * 48, "ADMIN_EMAILS": "adminVD@unklab.ac.id"},
            clear=True,
        ):
            with self.assertRaises(HTTPException) as error:
                main.login_with_password(
                    PasswordLogin(email="someone@gmail.com", password="any-password"),
                    self.request("localhost"),
                    Response(),
                )

        self.assertEqual(error.exception.status_code, 403)

    def test_password_login_uses_registered_student_hash(self):
        stored_hash = hash_password("student-test-password")
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = {
            "display_name": "Student Example",
            "role": "student",
            "password_hash": stored_hash,
        }
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "ADMIN_EMAILS": "adminVD@unklab.ac.id",
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ), patch("main.get_connection", return_value=connection_context):
            response = Response()
            user = main.login_with_password(
                PasswordLogin(
                    email="s22210609@student.unklab.ac.id",
                    password="student-test-password",
                ),
                self.request("localhost"),
                response,
            )

        self.assertEqual(user["role"], "student")
        self.assertTrue(response.headers["set-cookie"])

    def test_registration_requires_verified_student_and_saves_password_hash(self):
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = None
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection
        verified_user = {
            "email": "s22210609@student.unklab.ac.id",
            "name": "Student Example",
            "role": "student",
        }
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "s" * 48,
                "GOOGLE_CLIENT_ID": "test-client-id",
                "ADMIN_EMAILS": "adminVD@unklab.ac.id",
                "COOKIE_SECURE": "false",
                "COOKIE_SAMESITE": "lax",
            },
            clear=True,
        ), patch("main.verify_google_credential", return_value=verified_user), patch(
            "main.get_connection", return_value=connection_context
        ):
            response = Response()
            user = main.register_student(
                StudentRegistration(
                    credential="x" * 20,
                    email="S22210609@student.unklab.ac.id",
                    password="student-test-password",
                ),
                self.request("localhost"),
                response,
            )
            cookie_value = response.headers["set-cookie"].split(";", 1)[0]
            profile = main.read_current_user(
                current_user(self.request("localhost", cookie_value))
            )

        self.assertEqual(user["role"], "student")
        self.assertEqual(profile["email"], "s22210609@student.unklab.ac.id")
        registration_insert = connection.execute.call_args_list[1]
        self.assertIn("password_hash", registration_insert.args[0])
        self.assertNotIn("student-test-password", str(registration_insert.args))

    def test_registration_rejects_invalid_student_email_format(self):
        with self.assertRaises(ValueError):
            StudentRegistration(
                credential="x" * 20,
                email="student@student.unklab.ac.id",
                password="student-test-password",
            )
        self.assertEqual(
            StudentRegistration(
                credential="x" * 20,
                email="12410292@student.unklab.ac.id",
                password="student-test-password",
            ).email,
            "12410292@student.unklab.ac.id",
        )


if __name__ == "__main__":
    unittest.main()
