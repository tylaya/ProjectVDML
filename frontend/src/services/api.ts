import type { Application, ApplicationDecision, ApplicationInput, AuthUser, Dashboard, Inspection, InspectionInput, Kost, LoginRole, ModelInfo, QueueModulesResult, QueueSimulationInput, RegistrationPeriod, Settings, Student } from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? '';

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (!(init?.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers,
    });
  } catch {
    throw new Error('Backend tidak dapat dihubungi. Pastikan API berjalan di http://127.0.0.1:8000.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? `Permintaan gagal (${response.status}).`, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  me: () => request<AuthUser>('/api/auth/me'),
  login: (credential: string, email: string, requested_role: LoginRole) =>
    request<AuthUser>('/api/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential, email, requested_role }),
    }),
  passwordLogin: (email: string, password: string, requested_role?: LoginRole) =>
    request<AuthUser>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, ...(requested_role ? { requested_role } : {}) }),
    }),
  registerStudent: (credential: string, email: string, password: string) =>
    request<AuthUser>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ credential, email, password }),
    }),
  requestPasswordReset: (email: string) =>
    request<{ message: string }>('/api/auth/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, password: string) =>
    request<{ message: string }>('/api/auth/password-reset', {
      method: 'POST',
      body: JSON.stringify({ token, password }),
    }),
  logout: () => request<{ message: string }>('/api/auth/logout', { method: 'POST' }),
  myApplications: () => request<Application[]>('/api/applications/me'),
  submitApplication: (
    application: ApplicationInput,
    ktp: File | null,
    kartuKeluarga: File | null,
    residenceProof: File | null,
  ) => {
    const body = new FormData();
    body.append('payload', JSON.stringify(application));
    if (ktp) body.append('ktp', ktp);
    if (kartuKeluarga) body.append('kartu_keluarga', kartuKeluarga);
    if (residenceProof) {
      body.append(
        application.residence_type === 'Kost putra' || application.residence_type === 'Kost putri'
          ? 'surat_penerimaan_kost'
          : 'surat_domisili',
        residenceProof,
      );
    }
    return request<Application>('/api/applications/with-documents', { method: 'POST', body });
  },
  downloadApplicationDocument: async (
    id: number,
    documentType: 'ktp' | 'kartu_keluarga' | 'surat_penerimaan_kost' | 'surat_domisili',
  ) => {
    let response: Response;
    try {
      response = await fetch(
        `${API_URL}/api/applications/${id}/documents/${documentType}`,
        { credentials: 'include' },
      );
    } catch {
      throw new Error('Backend tidak dapat dihubungi. Pastikan API berjalan di http://127.0.0.1:8000.');
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { detail?: string } | null;
      throw new ApiError(body?.detail ?? `Unduhan gagal (${response.status}).`, response.status);
    }
    const blob = await response.blob();
    const extension = { 'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png' }[blob.type] ?? '';
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = `${documentType}-${id}${extension}`;
    window.document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
  approvedKosts: () => request<Omit<Kost, 'owner_email' | 'approval_status' | 'created_at' | 'updated_at'>[]>('/api/kosts/approved'),
  kosts: () => request<Kost[]>('/api/kosts'),
  createKost: (input: Pick<Kost, 'name' | 'address' | 'maps_url' | 'kelurahan' | 'residence_type' | 'owner_email'>) =>
    request<Kost>('/api/kosts', { method: 'POST', body: JSON.stringify(input) }),
  updateKostLocation: (id: number, maps_url: string) =>
    request<Kost>(`/api/kosts/${id}/location`, { method: 'PATCH', body: JSON.stringify({ maps_url }) }),
  decideKost: (id: number, approval_status: 'Disetujui' | 'Ditolak') =>
    request<Kost>(`/api/kosts/${id}/approval`, { method: 'PATCH', body: JSON.stringify({ approval_status }) }),
  ownerApplications: () => request<Application[]>('/api/owner/applications'),
  confirmKostOccupant: (id: number, status: 'Dikonfirmasi' | 'Ditolak', note: string) =>
    request<Application>(`/api/owner/applications/${id}/confirmation`, {
      method: 'PATCH',
      body: JSON.stringify({ status, note }),
    }),
  applications: () => request<Application[]>('/api/applications'),
  analyzeApplication: (id: number) =>
    request<Application>(`/api/applications/${id}/analyze`, { method: 'POST' }),
  decideApplication: (id: number, decision: ApplicationDecision) =>
    request<Application>(`/api/applications/${id}`, { method: 'PATCH', body: JSON.stringify(decision) }),
  dashboard: () => request<Dashboard>('/api/dashboard'),
  students: () => request<Student[]>('/api/students'),
  createStudent: (student: Omit<Student, 'id'> & { id: string }) =>
    request<Student>('/api/students', { method: 'POST', body: JSON.stringify(student) }),
  updateStudent: (id: string, student: Omit<Student, 'id'>) =>
    request<Student>(`/api/students/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(student) }),
  deleteStudent: (id: string) =>
    request<{ message: string }>(`/api/students/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  inspections: (search = '', status = '') => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (status) params.set('status', status);
    return request<Inspection[]>(`/api/inspections?${params.toString()}`);
  },
  analyze: (payload: InspectionInput) =>
    request<Inspection>('/api/inspections/analyze', { method: 'POST', body: JSON.stringify(payload) }),
  settings: () => request<Settings>('/api/settings'),
  saveSettings: (settings: Settings) =>
    request<Settings>('/api/settings', { method: 'PUT', body: JSON.stringify(settings) }),
  registrationPeriod: () => request<RegistrationPeriod>('/api/registration-period'),
  modelInfo: () => request<ModelInfo>('/api/ml/info'),
  queueDemo: (input: QueueSimulationInput) =>
    request<QueueModulesResult>('/api/ml/queue-demo', { method: 'POST', body: JSON.stringify(input) }),
};
