import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from location_analysis import parse_google_maps_coordinates


Category = Literal["Outsider Dekat", "Outsider Jauh"]
Status = Literal[
    "Sesuai Kategori",
    "Berpotensi Tidak Sesuai",
    "Perlu Verifikasi Petugas",
]
RoadAccess = Literal["Jalan Utama", "Lorong", "Perbukitan"]
ApplicationStatus = Literal["Menunggu verifikasi", "Perlu revisi", "Disetujui", "Ditolak"]
RequestType = Literal["Pendaftaran baru", "Perpanjangan"]
ResidenceType = Literal["Keluarga", "Wali", "Kost putra", "Kost putri"]


def normalize_residence_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Nama hunian dan area domisili tidak boleh kosong.")
    return normalized


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=20, max_length=10000)
    email: str = Field(min_length=3, max_length=254)
    requested_role: Literal["student", "admin", "kost_owner"]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    requested_role: Literal["student", "admin", "kost_owner"] | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class StudentRegistration(BaseModel):
    credential: str = Field(min_length=20, max_length=10000)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_student_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"s?\d{8}@student\.unklab\.ac\.id", normalized):
            raise ValueError(
                "Email mahasiswa harus berformat 12345678 atau s12345678@student.unklab.ac.id."
            )
        return normalized


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordReset(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class ApplicationCreate(BaseModel):
    request_type: RequestType
    category: Category
    residence_type: ResidenceType
    kost_id: int | None = Field(default=None, ge=1)
    semester: str = Field(min_length=3, max_length=40)
    nama_mahasiswa: str = Field(min_length=1, max_length=120)
    nama_kost: str = Field(min_length=1, max_length=120)
    alamat_kost: str = Field(min_length=1, max_length=240)
    kelurahan: str = Field(min_length=1, max_length=80)
    maps_url: str | None = Field(default=None, max_length=2048)
    jarak_km: float | None = Field(default=None, ge=0, le=100)
    waktu_tempuh_menit: int = Field(ge=1, le=1440)
    akses_jalan: RoadAccess

    @field_validator("semester")
    @classmethod
    def normalize_semester(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Semester tidak boleh kosong.")
        return normalized

    @field_validator("maps_url")
    @classmethod
    def validate_maps_url(cls, value: str | None) -> str | None:
        if value is not None:
            parse_google_maps_coordinates(value)
            return value.strip()
        return value


class ApplicationDecision(BaseModel):
    status: Literal["Perlu revisi", "Disetujui", "Ditolak"]
    admin_note: str = Field(min_length=3, max_length=500)

    @field_validator("admin_note")
    @classmethod
    def normalize_admin_note(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Catatan petugas minimal 3 karakter.")
        return normalized


class KostCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=5, max_length=240)
    kelurahan: str = Field(min_length=2, max_length=80)
    residence_type: Literal["Kost putra", "Kost putri"]
    owner_email: str = Field(min_length=3, max_length=254)
    maps_url: str = Field(min_length=12, max_length=2048)

    @field_validator("name", "address", "kelurahan")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_residence_text(value)

    @field_validator("maps_url")
    @classmethod
    def validate_maps_url(cls, value: str) -> str:
        normalized = value.strip()
        parse_google_maps_coordinates(normalized)
        return normalized

    @field_validator("owner_email")
    @classmethod
    def normalize_owner_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Email pemilik kost tidak valid.")
        return normalized


class KostApproval(BaseModel):
    approval_status: Literal["Disetujui", "Ditolak"]


class KostLocationUpdate(BaseModel):
    maps_url: str = Field(min_length=12, max_length=2048)

    @field_validator("maps_url")
    @classmethod
    def validate_maps_url(cls, value: str) -> str:
        normalized = value.strip()
        parse_google_maps_coordinates(normalized)
        return normalized


class KostConfirmation(BaseModel):
    status: Literal["Dikonfirmasi", "Ditolak"]
    note: str = Field(default="", max_length=500)


class StudentBase(BaseModel):
    nama_mahasiswa: str = Field(min_length=1, max_length=120)
    nama_kost: str = Field(min_length=1, max_length=120)
    alamat_kost: str = Field(min_length=1, max_length=240)
    kelurahan: str = Field(min_length=1, max_length=80)
    jarak_km: float = Field(ge=0, le=100)
    kategori_terdaftar: Category
    maps_url: str = Field(default="", max_length=2048)
    location_anomaly: bool = False

    @field_validator("nama_kost", "alamat_kost")
    @classmethod
    def normalize_residence_fields(cls, value: str) -> str:
        return normalize_residence_text(value)

    @field_validator("maps_url")
    @classmethod
    def validate_maps_url(cls, value: str) -> str:
        normalized = value.strip()
        if normalized:
            parse_google_maps_coordinates(normalized)
        return normalized


class StudentCreate(StudentBase):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9-]+$")


class StudentUpdate(StudentBase):
    pass


class Student(StudentCreate):
    model_config = ConfigDict(from_attributes=True)


class InspectionInput(BaseModel):
    student_id: str = Field(min_length=1, max_length=40)
    nama_mahasiswa: str = Field(min_length=1, max_length=120)
    nama_kost: str = Field(min_length=1, max_length=120)
    alamat_kost: str = Field(min_length=1, max_length=240)
    kelurahan: str = Field(min_length=1, max_length=80)
    jarak_km: float = Field(ge=0, le=100)
    waktu_tempuh_menit: int = Field(ge=1, le=600)
    akses_jalan: RoadAccess
    kategori_terdaftar: Category
    maps_url: str = Field(default="", max_length=2048)

    @field_validator("nama_kost", "alamat_kost")
    @classmethod
    def normalize_residence_fields(cls, value: str) -> str:
        return normalize_residence_text(value)

    @field_validator("maps_url")
    @classmethod
    def validate_maps_url(cls, value: str) -> str:
        normalized = value.strip()
        if normalized:
            parse_google_maps_coordinates(normalized)
        return normalized


class Settings(BaseModel):
    officer_name: str = Field(min_length=1, max_length=120)
    officer_title: str = Field(min_length=1, max_length=120)
    officer_unit: str = Field(min_length=1, max_length=160)
    confidence_threshold: float = Field(ge=0.5, le=0.99)
    distance_threshold_km: float = Field(gt=0, le=100)
    verification_zone_km: float = Field(ge=0, le=10)
    verification_zone_enabled: bool
    semester_name: str = Field(default="", max_length=40)
    semester_start_date: date | None = None
    campus_maps_url: str = Field(default="", max_length=2048)

    @field_validator("semester_name")
    @classmethod
    def normalize_semester_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("campus_maps_url")
    @classmethod
    def validate_campus_maps_url(cls, value: str) -> str:
        normalized = value.strip()
        if normalized:
            parse_google_maps_coordinates(normalized)
        return normalized


class QueueSimulationRequest(BaseModel):
    start_date: date
    service_counters: int = Field(default=2, ge=1, le=10)
    applicants_per_day: int = Field(default=24, ge=5, le=100)
    seed: int = Field(default=42, ge=0, le=999999)

    @field_validator("start_date")
    @classmethod
    def require_monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("Tanggal mulai simulasi harus hari Senin.")
        return value


class InspectionResult(InspectionInput):
    id: int
    prediksi_kategori: Category
    confidence_score: float = Field(ge=0, le=1)
    status: Status
    keterangan: str
    tanggal_pemeriksaan: str
