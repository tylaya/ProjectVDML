import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from auth import verify_google_credential
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

    def test_student_cannot_request_admin_role(self):
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
                    "google-token", "student@student.unklab.ac.id", "admin"
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


if __name__ == "__main__":
    unittest.main()
