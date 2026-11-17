# Software Requirements Specification — SIGAP-VD

**Sistem Informasi Pendaftaran dan Antrian Village Dean, Universitas Klabat**

- Versi: 0.2 (draft yang diselaraskan dengan implementasi saat ini)
- Status: prototype akademik; belum siap menerima data pribadi atau dokumen nyata
- **Terakhir diperbarui**: 2026-11-16 22:30:21 WITA
- Zona waktu Change Log: WITA (UTC+8)

## 1. Tujuan dan ruang lingkup

SIGAP-VD ditujukan untuk mengurangi penumpukan mahasiswa saat mendaftar atau memperpanjang
izin tinggal sebagai outsider. Produk akhir yang diharapkan mencakup portal mahasiswa,
dashboard staf/admin, pengajuan online, status pengajuan, pengelolaan kapasitas dan slot,
serta komponen Machine Learning untuk membantu perencanaan antrean. Keputusan kelayakan
tempat tinggal tetap milik staf Village Dean; prediksi ML tidak boleh menyetujui atau menolak
mahasiswa secara otomatis.

### Cakupan yang sudah berjalan di prototype

- Login Google ID token yang diverifikasi backend, session cookie, dan pembatasan mahasiswa
  versus staf/admin.
- Mahasiswa mengirim pengajuan dasar tanpa alamat lengkap atau unggahan dokumen, lalu melihat
  status dan catatan petugas miliknya sendiri.
- Staf/admin meninjau pengajuan dan mencatat keputusan; dashboard pemeriksaan hunian yang lama
  tetap tersedia untuk staf.
- Model yang ada mengklasifikasikan `Outsider Dekat`/`Outsider Jauh` dari dataset sintetis.
- Menu admin **Modul Antrean ML** menjalankan demo sintetis terpisah untuk M1–M8: estimasi
  durasi, moving-average permintaan, estimasi no-show, triase aturan sementara, checklist tanpa
  unggah, segmentasi operasional, anomaly flags, serta simulator offline FIFO/SPT/Q-learning.
- Asumsi waktu layanan awal dari pengguna: Senin–Jumat, 08.00–17.00; periode pendaftaran satu
  minggu di awal semester sebelum pembayaran uang kuliah dan kontrak mata kuliah. Tanggal,
  jumlah loket, volume aktual, dan aturan layanan masih parameter demo.

### Belum tersedia

Slot/tiket operasional, QR check-in, notifikasi, unggah dokumen, kalkulasi jarak/geocoding,
dashboard antrean real-time, scheduler operasional, audit viewer, dan penyimpanan terenkripsi.
M1–M8 yang ditambahkan hanya demonstrasi sintetis/offline; belum tervalidasi dengan data layanan
kampus dan bukan implementasi lengkap sistem antrean.

## 2. Aktor dan aturan

| Aktor | Hak dan tanggung jawab |
|---|---|
| Mahasiswa | Masuk dengan akun Google `@student.unklab.ac.id`, mengajukan pendaftaran, melihat pengajuan sendiri |
| Staf/admin | Alamat Google pada konfigurasi `ADMIN_EMAILS`; meninjau pengajuan dan menggunakan dashboard administrasi |
| ML | Memberikan estimasi/flag untuk membantu staf, tidak membuat keputusan administratif |

Aturan tempat tinggal (keluarga/wali atau kost khusus putra/putri, sesuai kebijakan resmi kampus)
harus menjadi validasi aturan yang dapat dijelaskan dan dikonfirmasi Village Dean. Aturan ini
tidak dipelajari dari label sintetis.

## 3. Kebutuhan fungsional

| ID | Kebutuhan | Status saat ini |
|---|---|---|
| FR-01 | Mahasiswa masuk menggunakan Google Workspace kampus; backend memverifikasi ID token dan membatasi domain mahasiswa | Implementasi awal; memerlukan OAuth Client ID |
| FR-02 | Hak akses dipisah berdasarkan peran mahasiswa dan staf/admin | Implementasi awal; staf memakai allowlist `ADMIN_EMAILS` |
| FR-03 | Mahasiswa mengirim pengajuan jenis, kategori dekat/jauh, tipe hunian, dan semester | Implementasi awal |
| FR-04 | Mahasiswa hanya dapat melihat riwayat/status pengajuan miliknya sendiri | Implementasi awal |
| FR-05 | Staf melihat antrean pengajuan dan menyimpan keputusan serta catatan | Implementasi awal; belum ada alur berkas |
| FR-06 | Sistem merekam audit login, pengajuan, dan keputusan dengan waktu UTC | Implementasi awal; belum ada UI audit |
| FR-07 | Staf mengelola data mahasiswa demo, menjalankan pemeriksaan kategori, melihat riwayat, dan mengubah pengaturan | Sudah ada, kini dilindungi peran staf |
| FR-08 | Sistem menerima dokumen domisili dengan validasi dan penyimpanan terenkripsi | Belum; wajib sebelum data nyata |
| FR-09 | Mahasiswa memesan/mengubah/membatalkan slot dan mendapat tiket virtual | Belum |
| FR-10 | Staf mengelola check-in, pemanggilan, penundaan, dan jalur walk-in | Belum |
| FR-11 | Papan antrean dan kapasitas layanan diperbarui secara real-time | Belum |
| FR-12 | Sistem mencatat durasi layanan, no-show, dan hasil untuk evaluasi | Belum; dibutuhkan sebelum model antrean supervised |
| FR-13 | Prediktor durasi layanan dibandingkan dengan baseline dan memakai data latih yang terlacak | Demo Random Forest vs median pada data sintetis; belum memakai data historis |
| FR-14 | Simulator membandingkan antrean manual, online+heuristik, dan online+ML | Simulator satu minggu sintetis membandingkan FIFO/SPT/RL offline; belum mensimulasikan sistem booking nyata |
| FR-15 | Scheduler ML/RL memiliki fallback FIFO/SPT dan tidak mengubah keputusan kelayakan | Q-learning eksperimental di simulator; FIFO/SPT pembanding, belum layak mengatur antrean nyata |
| FR-16 | Sub-agent change-logger memasukkan setiap perubahan ke Change Log melalui script WITA | Proses dokumentasi disiapkan di `.github/agents/` dan `tools/` |

## 4. Kebutuhan non-fungsional

| ID | Kategori | Kebutuhan / target awal | Verifikasi |
|---|---|---|---|
| NFR-01 | Keamanan | Sesi ditandatangani server, cookie HttpOnly/SameSite, HTTPS dan `COOKIE_SECURE=true` saat deploy | Uji konfigurasi dan sesi |
| NFR-02 | Otorisasi | Endpoint administrasi menolak mahasiswa; endpoint mahasiswa hanya mengembalikan data pemilik | Uji API per peran |
| NFR-03 | Privasi | Minimalkan data; jangan unggah dokumen/alamat nyata sebelum enkripsi, retensi, persetujuan, dan proses penghapusan tersedia | Review privasi |
| NFR-04 | Keandalan | Kegagalan model tidak menghentikan alur administratif; scheduler nantinya wajib fallback FIFO/SPT | Uji fallback |
| NFR-05 | Usability | UI berbahasa Indonesia, responsif desktop/HP, pesan status dan alasan mudah dipahami | UAT |
| NFR-06 | Performa | Target awal API non-ML p95 ≤ 2 detik dan inferensi ≤ 1 detik pada beban yang disepakati | Uji beban/benchmark |
| NFR-07 | Kualitas ML | Evaluasi pada data uji terpisah, bandingkan baseline, laporkan metrik dan asal data; jangan klaim performa lapangan dari data sintetis | Laporan eksperimen |
| NFR-08 | Human-in-the-loop | Keputusan approve/revisi/tolak hanya dapat dilakukan staf yang berwenang | Uji akses dan audit |
| NFR-09 | Reproducibility | Seed, versi dataset/model, konfigurasi, dan metrik eksperimen dicatat | Jalankan ulang pipeline |
| NFR-10 | Auditability | Perubahan sistem dicatat append-only di Change Log; keputusan operasional dicatat dalam audit log | Review berkala |

Target angka masih hipotesis dan perlu divalidasi dengan Village Dean serta pengukuran antrean
nyata yang dianonimkan.

## 5. Evaluasi keselarasan ML

Model sekarang **belum memecahkan masalah antrean**. Label dekat/jauh pada dataset 400 baris
dibuat sintetis dari jarak, waktu tempuh, dan aturan skor buatan; skor uji (macro-F1 0.870)
hanya mengukur konsistensi terhadap label buatan, bukan akurasi pada mahasiswa nyata. Jangan
memakai model ini untuk keputusan izin tinggal.

Status modul antrean pada menu demo:

| Modul | Implementasi demo | Batasan |
|---|---|---|
| M1 Service Time Predictor | Random Forest regression dan baseline median; MAE dilaporkan | Data sintetis, bukan durasi historis |
| M2 Demand Forecaster | Rata-rata harian/jam dari empat minggu sintetis, divalidasi pada minggu sintetis kelima dengan MAE | Bukan kalender/volume semester nyata |
| M3 No-Show Predictor | Logistic Regression; precision, recall, Brier score | Tidak untuk overbooking atau pembatasan layanan |
| M4 Eligibility Triage | Flag aturan jarak/checklist untuk tinjauan staf | Ambang aturan sementara; tidak memberi keputusan kelayakan/asrama |
| M5 Document Checker | Ringkasan kelengkapan checklist contoh | Tidak ada unggah; daftar resmi dan penyimpanan belum tersedia |
| M6 Segmentasi Pendaftar | Jalur standar, review, atau pelengkapan data | Segmen ilustratif, tidak membatasi akses |
| M7 Anomaly Detection | IsolationForest atas fitur sintetis | Flag bukan bukti kecurangan |
| M8 Smart Scheduler | Simulator satu minggu FIFO/SPT/Q-learning, termasuk metrik tunggu/fairness | Offline; belum lulus evaluasi fairness dan tidak mengatur antrean nyata |

Urutan ML yang direkomendasikan:

1. Kumpulkan event antrean yang dianonimkan dan definisikan target operasional.
2. Latih regresi durasi layanan (misalnya baseline median/Linear Regression lalu Random Forest
   atau Gradient Boosting); evaluasi MAE dan bias per kelompok relevan.
3. Buat simulator antrean dan bandingkan FIFO, SPT, serta kapasitas slot; ukur waktu tunggu,
   panjang antrean, utilisasi, no-show, dan jumlah mahasiswa terlayani.
4. Eksplorasi RL hanya di simulator dengan reward transparan, seed tetap, pembatasan fairness,
   dan fallback heuristik; bukan langsung pada antrean operasional.
5. Prioritaskan supervised learning dan heuristik yang dapat dijelaskan. Klasifikasi dekat/jauh
   tetap aturan konfigurasi resmi (mis. ambang jarak), bukan tugas ML, kecuali ada alasan dan
   label lapangan yang tervalidasi.

## 6. Batasan dan risiko sebelum pilot

- Google OAuth Client ID frontend dan backend harus sama; admin harus diset melalui allowlist.
- `SESSION_SECRET` harus rahasia, acak, dan minimal 32 karakter; jangan masukkan file `.env` ke Git.
- Deploy publik wajib HTTPS, `COOKIE_SECURE=true`, allowlist CORS yang sempit, backup, retensi,
  perlindungan database, dan peninjauan kebijakan UU PDP.
- SQLite prototype belum mengenkripsi data saat tersimpan. Jangan masukkan alamat, kontak wali,
  NIM, atau dokumen domisili nyata.
- Implementasi autentikasi ini adalah fondasi prototipe, bukan audit keamanan/sertifikasi kampus.

## 7. Change Log

Entri paling baru disisipkan tepat setelah marker. Timestamp dibuat oleh `tools/log_change.py`
dari jam sistem dalam zona WITA. Catat perubahan kode, data/model, konfigurasi, requirement,
dan dokumen.

<!-- CHANGELOG:START -->

### `[2026-11-16 22:30:21 WITA]` - Memperbaiki serialisasi hasil API simulasi
- **Tipe**: FIXED
- **Author**: change-logger
- **Fase**: 6
- **Requirement terkait**: FR-13, FR-14, FR-15, NFR-04, NFR-07
- **File**: `ml\queue_modules.py`, `backend\test_queue_modules.py`, `srs.md`
- **Detail**:
  - Menormalkan counter dan metrik no-show ke tipe JSON native agar endpoint FastAPI berhasil mengembalikan seluruh hasil M1-M8.
  - Uji endpoint dengan sesi admin sintetis berhasil mengembalikan HTTP 200; request tanpa sesi ditolak HTTP 401.
  - Sebanyak 12 tes backend lulus; build/type-check frontend berhasil.


### `[2026-11-16 22:15:17 WITA]` - Menguji login dan antrean sintetis
- **Tipe**: CHANGED
- **Author**: change-logger
- **Fase**: 6
- **Requirement terkait**: FR-01, FR-02, FR-13, FR-14, FR-15, NFR-02, NFR-07
- **File**: `frontend\src\pages\LoginPage.tsx`, `backend\test_auth.py`, `backend\test_queue_modules.py`
- **Detail**:
  - Memadatkan halaman login dengan tombol Masuk setelah email/peran dipilih dan mempertahankan tombol Google sebagai fallback.
  - Menambahkan tes autentikasi/triase/scheduler; 11 tes backend lulus dan build frontend sukses.
  - Memverifikasi endpoint demo antrean menolak pengguna tanpa sesi; Google OAuth nyata memerlukan Client ID/origin yang sah.


### `[2026-11-16 22:15:15 WITA]` - Menambahkan demo sintetis modul ML dan simulator antrean offline
- **Tipe**: ADDED
- **Author**: change-logger
- **Fase**: 4
- **Requirement terkait**: FR-13, FR-14, FR-15, NFR-04, NFR-07, NFR-09
- **File**: `ml\queue_modules.py`, `backend\main.py`, `backend\schemas.py`, `backend\test_queue_modules.py`, `frontend\src\App.tsx`, `frontend\src\components\Layout.tsx`, `frontend\src\pages\QueueModulesPage.tsx`, `frontend\src\services\api.ts`, `frontend\src\types.ts`, `WORKFLOW.md`, `README.md`
- **Detail**:
  - Menambahkan demo M1-M8 berbasis data sintetis, metrik evaluasi, checklist dokumen tanpa unggah, triase human-review, dan flag anomali.
  - Simulator satu minggu Senin-Jumat 08.00-17.00 membandingkan FIFO, SPT, dan Q-learning offline; hasil RL belum lulus gate fairness dan tidak mengatur antrean nyata.
  - Asumsi dua loket dan 80 pendaftar per hari hanya nilai demo; masa satu minggu awal semester mengikuti informasi pengguna, sedangkan kebijakan operasional lain menunggu konfirmasi.


### `[2026-11-16 21:02:41 WITA]` - Menyederhanakan login dengan tombol Masuk dan Google fallback
- **Tipe**: CHANGED
- **Author**: change-logger
- **Fase**: 5
- **Requirement terkait**: FR-01, FR-02, NFR-05
- **File**: `frontend\src\pages\LoginPage.tsx`, `README.md`
- **Detail**:
  - Menambahkan tombol Masuk untuk memulai Google One Tap setelah email dan peran dipilih.
  - Mempertahankan tombol Sign in with Google sebagai alternatif dan meringkas deskripsi halaman login.


### `[2026-11-15 20:03:15 WITA]` - Memperketat validasi pengajuan dan indikator antrean admin
- **Tipe**: FIXED
- **Author**: change-logger
- **Fase**: 5
- **Requirement terkait**: FR-03, FR-05, FR-06, NFR-02
- **File**: `backend\main.py`, `backend\schemas.py`, `frontend\src\components\Layout.tsx`
- **Detail**:
  - Teks kosong setelah spasi ditolak pada semester dan catatan keputusan.
  - Filter status pengajuan tidak dikenal menghasilkan respons 422, dan badge pengajuan menunggu tampil pada navigasi admin.


### `[2026-11-15 20:01:20 WITA]` - Menambahkan custom agent dan script pencatat perubahan WITA
- **Tipe**: ADDED
- **Author**: change-logger
- **Fase**: 0
- **Requirement terkait**: FR-16, NFR-10
- **File**: `.github\agents\change-logger.agent.md`, `tools\log_change.py`
- **Detail**:
  - Custom agent dibatasi untuk memverifikasi fakta dan mengubah Change Log srs.md hanya melalui script.
  - Script menghasilkan timestamp WITA dari jam sistem dan menyisipkan entri terbaru setelah marker.


### `[2026-11-15 20:01:13 WITA]` - Menyelaraskan SRS dan roadmap ML dengan kondisi proyek
- **Tipe**: DOCS
- **Author**: change-logger
- **Fase**: 0
- **Requirement terkait**: FR-13, FR-14, FR-15, NFR-07, NFR-09, NFR-10
- **File**: `srs.md`, `WORKFLOW.md`, `README.md`
- **Detail**:
  - SRS membedakan fitur yang berjalan dari fitur antrean dan ML yang belum ada.
  - Workflow memprioritaskan prediksi durasi supervised, simulator, FIFO/SPT, dan RL hanya sebagai eksperimen dengan fallback.
  - Keterbatasan dataset sintetis dekat/jauh dan kebutuhan validasi kebijakan Village Dean didokumentasikan.


### `[2026-11-15 20:01:01 WITA]` - Menambahkan autentikasi Google dan portal pengajuan mahasiswa/staf
- **Tipe**: ADDED
- **Author**: change-logger
- **Fase**: 5
- **Requirement terkait**: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, NFR-01, NFR-02, NFR-08
- **File**: `backend\auth.py`, `backend\main.py`, `backend\database.py`, `backend\schemas.py`, `backend\requirements.txt`, `backend\.env.example`, `frontend\.env.example`, `frontend\index.html`, `frontend\src\App.tsx`, `frontend\src\types.ts`, `frontend\src\services\api.ts`, `frontend\src\components\Layout.tsx`, `frontend\src\pages\LoginPage.tsx`, `frontend\src\pages\StudentPortalPage.tsx`, `frontend\src\pages\ApplicationsPage.tsx`, `frontend\src\vite-env.d.ts`
- **Detail**:
  - Backend memverifikasi Google ID token; peran staf berasal dari ADMIN_EMAILS dan sesi memakai cookie HttpOnly bertanda tangan.
  - Mahasiswa dapat mengirim dan melihat pengajuan sendiri; staf dapat meninjau dan mencatat keputusan serta audit dasar.
  - Autentikasi memerlukan konfigurasi OAuth; slot antrean, dokumen, dan enkripsi penyimpanan belum tersedia.

<!-- CHANGELOG:END -->
