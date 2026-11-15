from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Category = Literal["Outsider Dekat", "Outsider Jauh"]
Status = Literal[
    "Sesuai Kategori",
    "Berpotensi Tidak Sesuai",
    "Perlu Verifikasi Petugas",
]
RoadAccess = Literal["Jalan Utama", "Lorong", "Perbukitan"]


class StudentBase(BaseModel):
    nama_mahasiswa: str = Field(min_length=1, max_length=120)
    nama_kost: str = Field(min_length=1, max_length=120)
    alamat_kost: str = Field(min_length=1, max_length=240)
    kelurahan: str = Field(min_length=1, max_length=80)
    jarak_km: float = Field(ge=0, le=100)
    kategori_terdaftar: Category


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


class Settings(BaseModel):
    officer_name: str = Field(min_length=1, max_length=120)
    officer_title: str = Field(min_length=1, max_length=120)
    officer_unit: str = Field(min_length=1, max_length=160)
    confidence_threshold: float = Field(ge=0.5, le=0.99)
    distance_threshold_km: float = Field(gt=0, le=100)
    verification_zone_km: float = Field(ge=0, le=10)
    verification_zone_enabled: bool


class InspectionResult(InspectionInput):
    id: int
    prediksi_kategori: Category
    confidence_score: float = Field(ge=0, le=1)
    status: Status
    keterangan: str
    tanggal_pemeriksaan: str
