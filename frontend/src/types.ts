export type Category = 'Outsider Dekat' | 'Outsider Jauh';
export type VerificationStatus = 'Sesuai Kategori' | 'Berpotensi Tidak Sesuai' | 'Perlu Verifikasi Petugas';
export type Page = 'dashboard' | 'students' | 'inspection' | 'history' | 'settings';
export type RoadAccess = 'Jalan Utama' | 'Lorong' | 'Perbukitan';

export interface Student {
  id: string;
  nama_mahasiswa: string;
  nama_kost: string;
  alamat_kost: string;
  kelurahan: string;
  jarak_km: number;
  kategori_terdaftar: Category;
}

export interface Inspection {
  id: number;
  student_id: string;
  nama_mahasiswa: string;
  nama_kost: string;
  alamat_kost: string;
  kelurahan: string;
  jarak_km: number;
  waktu_tempuh_menit: number;
  akses_jalan: RoadAccess;
  kategori_terdaftar: Category;
  prediksi_kategori: Category;
  confidence_score: number;
  status: VerificationStatus;
  keterangan: string;
  tanggal_pemeriksaan: string;
}

export interface Settings {
  officer_name: string;
  officer_title: string;
  officer_unit: string;
  confidence_threshold: number;
  distance_threshold_km: number;
  verification_zone_km: number;
  verification_zone_enabled: boolean;
}

export interface Dashboard {
  total_mahasiswa: number;
  outsider_dekat: number;
  outsider_jauh: number;
  total_pemeriksaan: number;
  perlu_verifikasi: number;
  distribusi_kategori: Record<Category, number>;
  distribusi_status: Record<VerificationStatus, number>;
  pemeriksaan_terbaru: Inspection[];
}

export interface ModelInfo {
  status: 'ready' | 'unavailable';
  model_name: string;
  features: string[];
  metrics: { accuracy: number; precision: number; recall: number; f1_score: number } | null;
  message?: string;
}

export interface InspectionInput {
  student_id: string;
  nama_mahasiswa: string;
  nama_kost: string;
  alamat_kost: string;
  kelurahan: string;
  jarak_km: number;
  waktu_tempuh_menit: number;
  akses_jalan: RoadAccess;
  kategori_terdaftar: Category;
}
