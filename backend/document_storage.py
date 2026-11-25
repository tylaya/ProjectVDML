import os
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
DOCUMENT_TYPES = {
    "ktp": "KTP",
    "kartu_keluarga": "Kartu Keluarga",
    "surat_penerimaan_kost": "Surat bukti terdaftar di kost",
    "surat_domisili": "Surat keterangan domisili dari RT/RW atau pemerintah setempat",
}
DOCUMENT_FORMATS = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": (
        "image/png",
        lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ),
}


def _fernet() -> Fernet:
    key = os.environ.get("DOCUMENT_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "Dokumen belum dapat disimpan. Atur DOCUMENT_ENCRYPTION_KEY di backend."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise RuntimeError("DOCUMENT_ENCRYPTION_KEY tidak valid.") from error


def validate_document(filename: str, data: bytes) -> str:
    extension = Path(filename.replace("\\", "/")).suffix.lower()
    document_format = DOCUMENT_FORMATS.get(extension)
    if document_format is None:
        raise ValueError("Format berkas harus PDF, JPG, JPEG, atau PNG.")
    content_type, signature_check = document_format
    if not data or not signature_check(data):
        raise ValueError("Isi berkas tidak sesuai dengan format yang dipilih.")
    return content_type


def store_document(data: bytes) -> str:
    fernet = _fernet()
    storage_key = f"{uuid.uuid4()}.enc"
    storage_directory = Path(
        os.environ.get("DOCUMENT_STORAGE_DIR")
        or Path(__file__).resolve().parent / "private_documents"
    )
    storage_directory.mkdir(parents=True, exist_ok=True)
    (storage_directory / storage_key).write_bytes(fernet.encrypt(data))
    return storage_key


def read_document(storage_key: str) -> bytes:
    fernet = _fernet()
    try:
        storage_path = Path(storage_key)
        if (
            storage_path.suffix != ".enc"
            or f"{uuid.UUID(storage_path.stem)}.enc" != storage_key
        ):
            raise ValueError
    except ValueError as error:
        raise ValueError("Kunci penyimpanan dokumen tidak valid.") from error
    storage_directory = Path(
        os.environ.get("DOCUMENT_STORAGE_DIR")
        or Path(__file__).resolve().parent / "private_documents"
    )
    try:
        encrypted_data = (storage_directory / storage_key).read_bytes()
    except OSError as error:
        raise RuntimeError("Berkas dokumen tidak dapat dibaca dari penyimpanan.") from error
    try:
        return fernet.decrypt(encrypted_data)
    except InvalidToken as error:
        raise RuntimeError("Berkas dokumen tidak dapat didekripsi.") from error
