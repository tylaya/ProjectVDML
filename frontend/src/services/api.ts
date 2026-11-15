import type { Dashboard, Inspection, InspectionInput, ModelInfo, Settings, Student } from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new Error('Backend tidak dapat dihubungi. Pastikan API berjalan di http://localhost:8000.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Permintaan gagal (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
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
};
