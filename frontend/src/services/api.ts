import type { Application, ApplicationDecision, ApplicationInput, AuthUser, Dashboard, Inspection, InspectionInput, LoginRole, ModelInfo, QueueModulesResult, QueueSimulationInput, Settings, Student } from '../types';

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
  passwordLogin: (email: string, password: string) =>
    request<AuthUser>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  registerStudent: (credential: string, email: string, password: string) =>
    request<AuthUser>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ credential, email, password }),
    }),
  logout: () => request<{ message: string }>('/api/auth/logout', { method: 'POST' }),
  myApplications: () => request<Application[]>('/api/applications/me'),
  submitApplication: (
    application: ApplicationInput,
    ktp: File | null,
    kartuKeluarga: File | null,
  ) => {
    const body = new FormData();
    body.append('payload', JSON.stringify(application));
    if (ktp) body.append('ktp', ktp);
    if (kartuKeluarga) body.append('kartu_keluarga', kartuKeluarga);
    return request<Application>('/api/applications/with-documents', { method: 'POST', body });
  },
  downloadApplicationDocument: async (id: number, documentType: 'ktp' | 'kartu_keluarga') => {
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
  modelInfo: () => request<ModelInfo>('/api/ml/info'),
  queueDemo: (input: QueueSimulationInput) =>
    request<QueueModulesResult>('/api/ml/queue-demo', { method: 'POST', body: JSON.stringify(input) }),
};
