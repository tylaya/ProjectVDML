# Village Dean – Housing Verification System

Aplikasi demonstrasi full-stack untuk mendukung verifikasi administratif kategori hunian mahasiswa Universitas Klabat. Data awal dan dataset ML bersifat sintetis; aplikasi tidak memakai NIM, nomor WhatsApp, atau data pribadi asli. Prediksi model adalah rekomendasi untuk ditinjau petugas, bukan keputusan final.

## Struktur

- `frontend/`: React, TypeScript, Vite, Tailwind CSS, dan Lucide Icons.
- `backend/`: REST API FastAPI, validasi Pydantic, dan SQLite.
- `ml/`: generator dataset sintetis, evaluasi model scikit-learn, dan artefak model.

## Persyaratan

- Python 3.10–3.13
- Node.js 20 atau lebih baru dan npm

## 1. Buat dan evaluasi model ML

Dari direktori root proyek:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe ml\train_model.py
```

Training menggunakan dataset sintetis 400 baris di `ml/housing_dataset.csv`, membandingkan Random Forest dan Logistic Regression dengan train/test split, serta menampilkan accuracy, precision, recall, F1-score, dan confusion matrix. Model terbaik berdasarkan macro F1 tersimpan di `ml/artifacts/housing_model.joblib`; metrik perbandingan tersimpan di `ml/artifacts/model_metrics.json`. Backend juga mencoba menjalankan training otomatis bila artefak belum ada.

Jika model gagal dilatih atau dimuat, backend tetap dapat melayani dashboard, data mahasiswa, riwayat, dan pengaturan. Informasi kegagalan ditampilkan di dashboard; analisis ML dinonaktifkan sampai model siap.

## 2. Jalankan backend

Di Command Prompt, jalankan:

```cmd
cd backend
uvicorn main:app --reload
```

Perintah `uvicorn` menggunakan virtual environment proyek melalui pembungkus `backend\uvicorn.cmd`.

API tersedia di `http://localhost:8000`; dokumentasi interaktif ada di `http://localhost:8000/docs`. Database `backend/housing.db` dan seed mahasiswa/riwayat demonstrasi dibuat otomatis saat startup pertama. CORS diizinkan untuk `http://localhost:5173`.

## 3. Jalankan frontend

Buka terminal baru dari root proyek:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Buka URL yang ditampilkan Vite (default `http://localhost:5173`). Untuk pemeriksaan TypeScript dan production build, jalankan `npm run build`.

## Endpoint utama

- `GET /api/health`, `GET /api/dashboard`, `GET/POST/PUT/DELETE /api/students`
- `POST /api/inspections/analyze`, `GET /api/inspections?search=...&status=...`
- `GET/PUT /api/settings`, `GET /api/ml/info`

## Catatan demonstrasi

Model ini dilatih pada data buatan untuk keperluan proyek akademik dan bukan data survei lapangan. Hasil confidence tidak boleh dianggap sebagai kepastian; zona jarak dan ambang confidence hanya menandai data yang memerlukan peninjauan petugas. Data mahasiswa contoh menggunakan nama tampilan dan ID sintetis.
