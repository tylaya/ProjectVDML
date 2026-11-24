# Workflow Final Project Machine Learning — SIGAP-VD

## Sasaran

Mengurangi waktu tunggu pendaftaran outsider di Village Dean melalui pengajuan digital,
pengelolaan antrean berbasis data, dan rekomendasi ML yang tetap diawasi petugas. Persetujuan
tinggal di luar kampus adalah keputusan administratif manusia, bukan target otomasi ML.

## Alur layanan yang dituju

1. **Pra-pendaftaran mahasiswa** — mahasiswa membuat akun dengan email Google Workspace berformat
   `s` + 8 angka di `student.unklab.ac.id`, memverifikasinya melalui Google, lalu memilih
   pendaftaran baru/perpanjangan, kategori outsider, dan tipe hunian.
2. **Pemeriksaan kelengkapan** — sistem memeriksa field dan dokumen wajib; berkas sensitif
   hanya diproses setelah penyimpanan aman, retensi, serta akses kontrol disiapkan.
3. **Pra-triase berbasis aturan** — aturan kampus dan ambang dekat/jauh yang disahkan staf
   menghasilkan checklist atau flag; tidak melakukan approve/tolak otomatis.
4. **Penjadwalan** — sistem menyediakan slot berdasarkan jam kerja, kapasitas loket, durasi
   layanan perkiraan, kuota walk-in, dan penyangga no-show.
5. **Konfirmasi dan tiket** — mahasiswa memperoleh waktu layanan, estimasi, dan tiket/QR;
   pengingat serta reschedule mengikuti kebijakan yang dikonfirmasi.
6. **Kedatangan** — staf scan QR atau mencari tiket, menangani walk-in, memanggil mahasiswa,
   mencatat mulai/selesai layanan dan no-show.
7. **Keputusan** — staf memeriksa dokumen dan rekomendasi, lalu memilih disetujui, revisi,
   ditolak, atau diarahkan ke asrama beserta alasan; override ML dicatat.
8. **Evaluasi** — dashboard membandingkan waktu tunggu, durasi, utilisasi, no-show, beban
   staf, dan fairness antar kelompok; hasil digunakan untuk iterasi, bukan menghukum mahasiswa.

## Roadmap fase 0–7

| Fase | Pekerjaan | Metode / hasil | Gate untuk lanjut |
|---|---|---|---|
| 0 — Discovery | Wawancara Village Dean; validasi kebijakan, volume puncak, jumlah loket, jam layanan, durasi, kuota walk-in, dokumen | SRS, data dictionary, definisi metrik, pemetaan proses saat ini | Pemilik proses menyetujui aturan dan alur |
| 1 — Fondasi data | Rancang event log, consent, minimisasi data, anonimisasi, pemisahan data demo dan nyata | Skema aplikasi/antrian; generator sintetis khusus simulasi | Kebijakan privasi dan sumber data jelas |
| 2 — Baseline supervised | Uji regresi durasi layanan dari event historis; prediksi permintaan opsional | Median/Linear Regression sebagai baseline; bandingkan Random Forest/Gradient Boosting; MAE/median absolute error | Data cukup, leakage diperiksa, model mengalahkan baseline |
| 3 — Unsupervised/triase | Eksplorasi pola beban atau jalur pelayanan; aturan kelengkapan tetap deterministik | K-means hanya jika klaster actionable; anomaly detection hanya sebagai flag tinjauan | Staf memahami kegunaan klaster/flag dan tidak ada penolakan otomatis |
| 4 — Simulator antrean & RL | Simulasikan FIFO, SPT, online+heuristik, dan kebijakan RL | Seed tetap; reward mencakup waktu tunggu, fairness, idle time, kapasitas, no-show; fallback FIFO/SPT | RL mengungguli baseline pada beberapa seed dan skenario, tidak merugikan kelompok |
| 5 — Integrasi produk | Integrasi portal mahasiswa/staf, autentikasi/otorisasi, pengajuan, slot, check-in, notifikasi, audit | REST API, database terkelola, RBAC, mode manual cadangan | Security/privacy review dan UAT lulus |
| 6 — Pengujian & evaluasi | Uji fungsional, akses, performa, usability, fairness, simulasi gangguan | Perbandingan antrean sebelum/sesudah dan baseline; dokumentasikan keterbatasan | Target disetujui pengguna dan hasil dapat direproduksi |
| 7 — Finalisasi | Dokumentasi, demo, model card, laporan hasil, batasan, dan rekomendasi implementasi | Reproducible runbook dan presentasi | Tidak ada klaim performa lapangan dari data sintetis |

## Pilihan metode ML

| Masalah | Pilihan awal | Catatan keputusan |
|---|---|---|
| Estimasi durasi layanan | Supervised regression; baseline median dan Linear Regression, kandidat Random Forest/Gradient Boosting | Gunakan fitur operasional yang tersedia sebelum pelayanan; target MAE, bukan akurasi klasifikasi |
| Prediksi beban per jam/hari | Moving average sebagai baseline, lalu regresi/time-series jika riwayat memadai | Tidak wajib pada MVP; hindari prediksi jika data sangat sedikit |
| No-show | Logistic Regression/Gradient Boosting dengan kalibrasi probabilitas | Opsional; overbooking tidak boleh menghilangkan hak mahasiswa atas slot |
| Kelayakan tempat tinggal | Rule engine berdasarkan kebijakan resmi, human review | Bukan RL/unsupervised; tidak melatih keputusan sensitif dari label historis tanpa validasi |
| Segmentasi jalur layanan | K-means hanya untuk eksplorasi operasional | Harus dapat dijelaskan dan tidak membatasi akses layanan |
| Urutan layanan | FIFO/SPT sebagai baseline; RL hanya di simulator | Tidak menjalankan eksplorasi kebijakan pada mahasiswa nyata |

## Status terhadap implementasi saat ini

- Tersedia: staff dashboard untuk kategori hunian, data/riwayat pemeriksaan, pengaturan ambang
  jarak, autentikasi Google dan password dengan allowlist admin, pendaftaran akun mahasiswa
  terverifikasi Google, portal submit/status pengajuan dasar, dan audit log sederhana.
- Demo sintetis pada menu **Modul Antrean ML**: M1 regresi durasi dengan pembanding median; M2
  moving-average beban per hari/jam dari empat minggu sintetis dengan validasi minggu kelima;
  M3 logistic regression no-show;
  M4 triase aturan sementara; M5 checklist contoh tanpa berkas; M6 segmentasi jalur yang dapat
  dijelaskan; M7 IsolationForest; M8 simulator offline FIFO/SPT/Q-learning.
- Parameter awal yang diinformasikan pengguna: layanan Senin–Jumat pukul 08.00–17.00 dan
  pendaftaran satu minggu pada awal semester sebelum pembayaran uang kuliah/kontrak mata kuliah.
  Tanggal tepat, loket, volume, kebijakan dokumen, dan aturan kategori masih perlu konfirmasi.
- Demo di atas tidak membuat booking/tiket dan tidak menggunakan data mahasiswa nyata. Belum
  tersedia: slot operasional, QR/check-in, penyimpanan dokumen, notifikasi, live queue, audit
  viewer, dan model antrean yang dilatih atau divalidasi dengan data historis kampus.
- Model classifier dekat/jauh saat ini memakai label sintetis. Pertahankan hanya sebagai demo
  pipeline ML; jangan jadikan bukti bahwa antrean telah terselesaikan.

## Metrik evaluasi

- **Operasional:** median dan p90 waktu tunggu, panjang antrean maksimum, waktu layanan, utilisasi
  loket, no-show, walk-in terlayani, dan jumlah mahasiswa terlayani per hari.
- **ML:** MAE/RMSE untuk durasi; MAE/weighted error untuk permintaan; precision/recall dan
  calibration untuk no-show; perbandingan terhadap baseline.
- **Keadilan & layanan:** metrik waktu tunggu/akses per kategori dan kelompok relevan yang
  disetujui kampus; hindari atribut sensitif jika tidak ada dasar penggunaan.
- **Eksperimen:** dokumentasikan seed, split temporal, periode data, fitur yang tersedia saat
  prediksi, model, baseline, dan keterbatasan.

## Asumsi yang menunggu konfirmasi Village Dean/dosen

1. Definisi resmi outsider dekat/jauh dan pemilik perubahan ambangnya.
2. Kategori hunian yang sah serta alur revisi/tolak/arah asrama.
3. Volume pendaftaran semester, jumlah petugas/loket, jam layanan, dan target waktu tunggu.
4. Kapasitas walk-in, aturan no-show, pembatalan, perubahan slot, dan prioritas yang diperbolehkan.
5. Daftar dokumen dan mekanisme penyimpanan, retensi, akses, koreksi, serta penghapusan data.
6. Data historis yang tersedia, dasar pemrosesan, proses anonimisasi, dan izin penggunaannya.
7. Tahapan dosen dan deliverable per pertemuan (belum diisi karena jadwal belum diberikan).
