export type Category = 'Outsider Dekat' | 'Outsider Jauh';
export type VerificationStatus = 'Sesuai Kategori' | 'Berpotensi Tidak Sesuai' | 'Perlu Verifikasi Petugas';
export type Page = 'dashboard' | 'students' | 'inspection' | 'history' | 'settings' | 'applications' | 'queueModules' | 'kosts';
export type RoadAccess = 'Jalan Utama' | 'Lorong' | 'Perbukitan';
export type LoginRole = 'student' | 'admin' | 'kost_owner';

export interface AuthUser {
  email: string;
  name: string;
  role: 'student' | 'admin' | 'kost_owner';
}

export interface Kost {
  id: number;
  name: string;
  address: string;
  maps_url: string;
  kelurahan: string;
  residence_type: 'Kost putra' | 'Kost putri';
  owner_email: string;
  approval_status: 'Menunggu approval' | 'Disetujui' | 'Ditolak';
  location_anomaly: boolean | 0 | 1;
  created_at: string;
  updated_at: string;
}

export interface Application {
  id: number;
  student_email: string;
  request_type: 'Pendaftaran baru' | 'Perpanjangan';
  category: Category;
  residence_type: 'Keluarga' | 'Wali' | 'Kost putra' | 'Kost putri';
  kost_id: number | null;
  kost_confirmation_status: 'Tidak diperlukan' | 'Menunggu kost' | 'Dikonfirmasi' | 'Ditolak';
  kost_confirmation_note: string;
  semester: string;
  nama_mahasiswa: string;
  nama_kost: string;
  alamat_kost: string;
  maps_url: string;
  kelurahan: string;
  jarak_km: number;
  waktu_tempuh_menit: number;
  akses_jalan: RoadAccess;
  ml_prediction: '' | Category;
  ml_confidence: number;
  ml_status: string;
  ml_eligible: number;
  status: 'Menunggu verifikasi' | 'Perlu revisi' | 'Disetujui' | 'Ditolak';
  admin_note: string;
  documents: ('ktp' | 'kartu_keluarga' | 'surat_penerimaan_kost' | 'surat_domisili')[];
  created_at: string;
  updated_at: string;
}

export type ApplicationInput = Pick<
  Application,
  'request_type' | 'category' | 'residence_type' | 'semester' | 'nama_mahasiswa' |
  'nama_kost' | 'alamat_kost' | 'kelurahan' | 'jarak_km' | 'waktu_tempuh_menit' | 'akses_jalan' | 'kost_id'
  | 'maps_url'
>;
export type ApplicationDecision = Pick<Application, 'status' | 'admin_note'>;

export interface Student {
  id: string;
  nama_mahasiswa: string;
  nama_kost: string;
  alamat_kost: string;
  maps_url: string;
  kelurahan: string;
  jarak_km: number;
  kategori_terdaftar: Category;
  location_anomaly: boolean;
}

export interface Inspection {
  id: number;
  student_id: string;
  nama_mahasiswa: string;
  nama_kost: string;
  alamat_kost: string;
  maps_url: string;
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
  semester_name: string;
  semester_start_date: string | null;
  campus_maps_url: string;
}

export interface RegistrationPeriod {
  configured: boolean;
  location_configured: boolean;
  semester_name: string;
  start_date: string | null;
  end_date: string | null;
  is_open: boolean;
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
  maps_url: string;
  kelurahan: string;
  jarak_km: number;
  waktu_tempuh_menit: number;
  akses_jalan: RoadAccess;
  kategori_terdaftar: Category;
}

export interface QueueSimulationInput {
  start_date: string;
  service_counters: number;
  applicants_per_day: number;
  seed: number;
}

export interface QueuePolicyResult {
  label: string;
  served: number;
  no_shows: number;
  mean_wait_minutes: number;
  p90_wait_minutes: number;
  max_wait_minutes: number;
  max_queue: number;
  overtime_minutes: number;
  wait_gap_minutes: number;
}

export interface QueueModulesResult {
  mode: string;
  seed: number;
  period: {
    start_date: string;
    end_date: string;
    service_days: string[];
    hours: string;
    service_counters: number;
    applicants_per_day: number;
  };
  notice: string;
  modules: {
    M1: {
      status: string;
      model: string;
      mae_minutes: number;
      baseline_mae_minutes: number;
      mean_predicted_duration_minutes: number;
      sample_count: number;
    };
    M2: {
      status: string;
      method: string;
      daily_mae_validation: number;
      hourly_mae_validation: number;
      forecast: { weekday: string; expected_applicants: number; peak_hour: string; hourly_counts: number[] }[];
      forecast_total: number;
    };
    M3: {
      status: string;
      model: string;
      precision: number;
      recall: number;
      brier_score: number;
      predicted_no_show_rate: number;
      simulated_no_shows: number;
      sample_count: number;
    };
    M4: {
      status: string;
      recommendations: Record<string, number>;
      distance_threshold_km: number;
      review_zone_km: number;
      note: string;
    };
    M5: {
      status: string;
      documents: string[];
      complete_count: number;
      incomplete_count: number;
      document_checklist: Record<string, { provided: number; missing: number }>;
      note: string;
    };
    M6: {
      status: string;
      segments: Record<string, number>;
      note: string;
    };
    M7: {
      status: string;
      method: string;
      flagged_count: number;
      sample_count: number;
      flags: { id: string; reasons: string[] }[];
      note: string;
    };
    M8: {
      status: string;
      episodes: number;
      policies: Record<'fifo' | 'spt' | 'rl', QueuePolicyResult>;
      note: string;
    };
  };
  applicant_samples: {
    id: string;
    category: Category;
    distance_km: number;
    documents_complete: boolean;
    recommendation: string;
    segment: string;
  }[];
}
