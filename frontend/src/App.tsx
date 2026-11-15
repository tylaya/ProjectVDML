import { useCallback, useEffect, useState } from 'react';
import { Layout } from './components/Layout';
import { api } from './services/api';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { InspectionPage } from './pages/InspectionPage';
import { SettingsPage } from './pages/SettingsPage';
import { StudentsPage } from './pages/StudentsPage';
import type { Dashboard, Inspection, InspectionInput, ModelInfo, Page, Settings, Student } from './types';

const initialSettings: Settings = { officer_name: 'Petugas Demo', officer_title: 'Verifikator Hunian', officer_unit: 'Village Dean — Universitas Klabat', confidence_threshold: 0.65, distance_threshold_km: 2, verification_zone_km: 0.2, verification_zone_enabled: true };
export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [settings, setSettings] = useState<Settings>(initialSettings);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const refreshDashboard = useCallback(async () => setDashboard(await api.dashboard()), []);
  const refreshStudents = useCallback(async () => setStudents(await api.students()), []);
  const loadPageData = useCallback(async (showLoading = true) => {
    if (showLoading) { setLoading(true); setError(''); }
    try {
      const [health, dashboardData, studentData, settingsData, modelData] = await Promise.all([
        api.health(), api.dashboard(), api.students(), api.settings(), api.modelInfo(),
      ]);
      if (health.status !== 'ok') throw new Error('Backend belum siap.');
      setError(''); setDashboard(dashboardData); setStudents(studentData); setSettings(settingsData); setModel(modelData);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Aplikasi gagal memuat data.'); }
    finally { if (showLoading) setLoading(false); }
  }, []);
  useEffect(() => { void loadPageData(); }, [loadPageData]);
  useEffect(() => {
    if (loading || !error || dashboard) return;
    let active = true;
    let timer: number;
    const retry = async () => {
      await loadPageData(false);
      if (active) timer = window.setTimeout(retry, 3000);
    };
    timer = window.setTimeout(retry, 3000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [dashboard, error, loadPageData, loading]);
  const run = async (operation: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await operation(); } catch (reason) { const message = reason instanceof Error ? reason.message : 'Permintaan gagal.'; setError(message); throw reason; }
    finally { setBusy(false); }
  };
  const saveSettings = async (value: Settings) => run(async () => { setSettings(await api.saveSettings(value)); });
  const createStudent = async (item: Omit<Student, 'id'> & { id: string }) => run(async () => { await api.createStudent(item); await refreshStudents(); await refreshDashboard(); });
  const updateStudent = async (id: string, item: Omit<Student, 'id'>) => run(async () => { await api.updateStudent(id, item); await refreshStudents(); await refreshDashboard(); });
  const deleteStudent = async (id: string) => run(async () => { await api.deleteStudent(id); await refreshStudents(); await refreshDashboard(); });
  const analyze = async (data: InspectionInput): Promise<Inspection> => {
    let result!: Inspection;
    await run(async () => { result = await api.analyze(data); await Promise.all([refreshDashboard(), refreshStudents()]); });
    return result;
  };
  const loadInspections = useCallback((search: string, status: string) => api.inspections(search, status), []);
  if (loading) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Menghubungkan ke Village Dean API…</div>;
  if (error && !dashboard) return <div className="mx-auto mt-20 max-w-lg rounded-2xl border bg-white p-8 text-center"><h1 className="text-xl font-bold text-royal">Backend belum tersedia</h1><p role="alert" className="my-4 text-sm text-rose-700">{error}</p><p className="mb-4 text-sm text-slate-500">Aplikasi mencoba menyambung kembali otomatis setiap 3 detik.</p><button onClick={() => void loadPageData()} className="rounded-lg bg-royal px-4 py-2 text-sm text-white">Coba lagi</button></div>;
  if (!dashboard || !model) return null;
  return <Layout page={page} onNavigate={setPage} settings={settings} pending={dashboard.perlu_verifikasi}>
    {error && <div role="alert" className="mb-5 flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"><span>{error}</span><button onClick={() => setError('')} aria-label="Tutup pesan">×</button></div>}
    {page === 'dashboard' && <DashboardPage data={dashboard} model={model} navigate={setPage} />}
    {page === 'students' && <StudentsPage students={students} onCreate={createStudent} onUpdate={updateStudent} onDelete={deleteStudent} busy={busy} />}
    {page === 'inspection' && <InspectionPage students={students} onAnalyze={analyze} busy={busy} modelAvailable={model.status === 'ready'} modelMessage={model.message} />}
    {page === 'history' && <HistoryPage loadInspections={loadInspections} />}
    {page === 'settings' && <SettingsPage settings={settings} onSave={saveSettings} busy={busy} />}
  </Layout>;
}
