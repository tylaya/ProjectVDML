import { useCallback, useEffect, useState } from 'react';
import { Layout } from './components/Layout';
import { api } from './services/api';
import { ApiError } from './services/api';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { LoginPage } from './pages/LoginPage';
import { StudentPortalPage } from './pages/StudentPortalPage';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { InspectionPage } from './pages/InspectionPage';
import { SettingsPage } from './pages/SettingsPage';
import { StudentsPage } from './pages/StudentsPage';
import { QueueModulesPage } from './pages/QueueModulesPage';
import { KostsPage } from './pages/KostsPage';
import { KostOwnerPage } from './pages/KostOwnerPage';
import type { Application, ApplicationDecision, ApplicationInput, AuthUser, Dashboard, Inspection, InspectionInput, Kost, LoginRole, ModelInfo, Page, QueueSimulationInput, RegistrationPeriod, Settings, Student } from './types';

const initialSettings: Settings = { officer_name: 'Petugas Demo', officer_title: 'Verifikator Hunian', officer_unit: 'Village Dean — Universitas Klabat', confidence_threshold: 0.65, distance_threshold_km: 2, verification_zone_km: 0.2, verification_zone_enabled: true, semester_name: '', semester_start_date: null, campus_maps_url: '' };
export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [kosts, setKosts] = useState<Kost[]>([]);
  const [approvedKosts, setApprovedKosts] = useState<Pick<Kost, 'id' | 'name' | 'address' | 'maps_url' | 'kelurahan' | 'residence_type'>[]>([]);
  const [settings, setSettings] = useState<Settings>(initialSettings);
  const [registrationPeriod, setRegistrationPeriod] = useState<RegistrationPeriod>({
    configured: false,
    location_configured: false,
    semester_name: '',
    start_date: null,
    end_date: null,
    is_open: false,
  });
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const refreshDashboard = useCallback(async () => setDashboard(await api.dashboard()), []);
  const refreshStudents = useCallback(async () => setStudents(await api.students()), []);
  const refreshApplications = useCallback(async () => setApplications(user?.role === 'admin' ? await api.applications() : await api.myApplications()), [user]);
  const refreshKosts = useCallback(async () => setKosts(await api.kosts()), []);
  const refreshOwnerApplications = useCallback(async () => setApplications(await api.ownerApplications()), []);
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
  useEffect(() => {
    let active = true;
    api.me().then(profile => {
      if (active) setUser(profile);
    }).catch(reason => {
      if (!active) return;
      if (reason instanceof ApiError && reason.status === 401) setUser(null);
      else setError(reason instanceof Error ? reason.message : 'Sesi gagal diperiksa.');
    }).finally(() => {
      if (active) { setAuthChecked(true); setLoading(false); }
    });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!user) return;
    if (user.role === 'admin') {
      void loadPageData();
      void refreshApplications().catch(reason => setError(reason instanceof Error ? reason.message : 'Daftar pengajuan gagal dimuat.'));
      void refreshKosts().catch(reason => setError(reason instanceof Error ? reason.message : 'Daftar kost gagal dimuat.'));
    } else if (user.role === 'student') {
      setLoading(true);
      Promise.all([
        refreshApplications(),
        api.approvedKosts().then(setApprovedKosts),
        api.registrationPeriod().then(setRegistrationPeriod),
      ])
        .catch(reason => setError(reason instanceof Error ? reason.message : 'Data portal mahasiswa gagal dimuat.'))
        .finally(() => setLoading(false));
    } else {
      setLoading(true);
      refreshOwnerApplications().catch(reason => setError(reason instanceof Error ? reason.message : 'Daftar penghuni kost gagal dimuat.'))
        .finally(() => setLoading(false));
    }
  }, [user, loadPageData, refreshApplications, refreshKosts, refreshOwnerApplications]);
  useEffect(() => {
    if (!user || user.role !== 'admin' || loading || !error || dashboard) return;
    let active = true;
    let timer: number;
    const retry = async () => {
      await loadPageData(false);
      if (active) timer = window.setTimeout(retry, 3000);
    };
    timer = window.setTimeout(retry, 3000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [dashboard, error, loadPageData, loading, user]);
  const run = async (operation: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await operation(); } catch (reason) { const message = reason instanceof Error ? reason.message : 'Permintaan gagal.'; setError(message); throw reason; }
    finally { setBusy(false); }
  };
  const saveSettings = async (value: Settings) => run(async () => { setSettings(await api.saveSettings(value)); });
  const submitApplication = async (value: ApplicationInput, ktp: File | null, kartuKeluarga: File | null, residenceProof: File | null) => run(async () => {
    await api.submitApplication(value, ktp, kartuKeluarga, residenceProof);
    await refreshApplications();
  });
  const decideApplication = async (id: number, decision: ApplicationDecision) => run(async () => {
    await api.decideApplication(id, decision);
    if (decision.status === 'Disetujui') {
      await Promise.all([refreshApplications(), refreshStudents(), refreshDashboard()]);
    } else {
      await refreshApplications();
    }
  });
  const downloadApplicationDocument = async (id: number, documentType: 'ktp' | 'kartu_keluarga' | 'surat_penerimaan_kost' | 'surat_domisili') => run(async () => {
    await api.downloadApplicationDocument(id, documentType);
  });
  const createKost = async (item: Pick<Kost, 'name' | 'address' | 'maps_url' | 'kelurahan' | 'residence_type' | 'owner_email'>) => run(async () => {
    await api.createKost(item);
    await refreshKosts();
  });
  const updateKostLocation = async (id: number, mapsUrl: string) => run(async () => {
    await api.updateKostLocation(id, mapsUrl);
    await Promise.all([refreshKosts(), api.approvedKosts().then(setApprovedKosts)]);
  });
  const decideKost = async (id: number, status: 'Disetujui' | 'Ditolak') => run(async () => {
    await api.decideKost(id, status);
    await Promise.all([refreshKosts(), api.approvedKosts().then(setApprovedKosts)]);
  });
  const confirmKostOccupant = async (id: number, status: 'Dikonfirmasi' | 'Ditolak', note: string) => run(async () => {
    await api.confirmKostOccupant(id, status, note);
    await refreshOwnerApplications();
  });
  const analyzeApplication = async (id: number): Promise<Application> => {
    let updated!: Application;
    await run(async () => {
      updated = await api.analyzeApplication(id);
      await refreshApplications();
    });
    return updated;
  };
  const createStudent = async (item: Omit<Student, 'id'> & { id: string }) => run(async () => { await api.createStudent(item); await refreshStudents(); await refreshDashboard(); });
  const updateStudent = async (id: string, item: Omit<Student, 'id'>) => run(async () => { await api.updateStudent(id, item); await refreshStudents(); await refreshDashboard(); });
  const deleteStudent = async (id: string) => run(async () => { await api.deleteStudent(id); await refreshStudents(); await refreshDashboard(); });
  const analyze = async (data: InspectionInput): Promise<Inspection> => {
    let result!: Inspection;
    await run(async () => { result = await api.analyze(data); await Promise.all([refreshDashboard(), refreshStudents()]); });
    return result;
  };
  const loadInspections = useCallback((search: string, status: string) => api.inspections(search, status), []);
  const runQueueDemo = async (input: QueueSimulationInput) => {
    let result!: Awaited<ReturnType<typeof api.queueDemo>>;
    await run(async () => { result = await api.queueDemo(input); });
    return result;
  };
  const establishSession = async () => {
    const profile = await api.me();
    setError('');
    setUser(profile);
    setPage(profile.role === 'admin' ? 'dashboard' : 'applications');
  };
  const login = async (credential: string, email: string, requestedRole: LoginRole) => {
    await api.login(credential, email, requestedRole);
    await establishSession();
  };
  const passwordLogin = async (email: string, password: string, requestedRole?: LoginRole) => {
    await api.passwordLogin(email, password, requestedRole);
    await establishSession();
  };
  const registerStudent = async (credential: string, email: string, password: string) => {
    await api.registerStudent(credential, email, password);
    await establishSession();
  };
  const requestPasswordReset = async (email: string) => { await api.requestPasswordReset(email); };
  const resetPassword = async (token: string, password: string) => { await api.resetPassword(token, password); };
  const logout = async () => {
    try {
      await api.logout();
      setUser(null); setDashboard(null); setApplications([]); setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sesi gagal diakhiri.');
    }
  };
  if (!authChecked || loading) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Memeriksa sesi Village Dean…</div>;
  if (error && !user) return <div className="mx-auto mt-20 max-w-lg rounded-2xl border bg-white p-8 text-center"><h1 className="text-xl font-bold text-royal">Layanan belum tersedia</h1><p role="alert" className="my-4 text-sm text-rose-700">{error}</p><button onClick={() => window.location.reload()} className="rounded-lg bg-royal px-4 py-2 text-sm text-white">Coba lagi</button></div>;
  if (!user) {
    return (
      <LoginPage
        onPasswordLogin={passwordLogin}
        onGoogleLogin={login}
        onRegister={registerStudent}
        onRequestPasswordReset={requestPasswordReset}
        onResetPassword={resetPassword}
      />
    );
  }
  if (user.role === 'student') return <StudentPortalPage user={user} applications={applications} kosts={approvedKosts} registrationPeriod={registrationPeriod} onSubmit={submitApplication} onLogout={() => void logout()} busy={busy} error={error} />;
  if (user.role === 'kost_owner') return <KostOwnerPage user={user} applications={applications} onConfirm={confirmKostOccupant} onLogout={() => void logout()} busy={busy} error={error} />;
  if (error && !dashboard) return <div className="mx-auto mt-20 max-w-lg rounded-2xl border bg-white p-8 text-center"><h1 className="text-xl font-bold text-royal">Dashboard petugas belum tersedia</h1><p role="alert" className="my-4 text-sm text-rose-700">{error}</p><button onClick={() => void loadPageData()} className="rounded-lg bg-royal px-4 py-2 text-sm text-white">Coba lagi</button></div>;
  if (!dashboard || !model) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Memuat dashboard petugas…</div>;
  return <Layout page={page} onNavigate={setPage} settings={settings} pending={applications.filter(item => item.status === 'Menunggu verifikasi').length} onLogout={() => void logout()}>
    {error && <div role="alert" className="mb-5 flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"><span>{error}</span><button onClick={() => setError('')} aria-label="Tutup pesan">×</button></div>}
    {page === 'dashboard' && <DashboardPage data={dashboard} model={model} navigate={setPage} />}
    {page === 'applications' && <ApplicationsPage applications={applications} onAnalyze={analyzeApplication} onDecide={decideApplication} onDownloadDocument={downloadApplicationDocument} busy={busy} />}
    {page === 'kosts' && <KostsPage kosts={kosts} onCreate={createKost} onUpdateLocation={updateKostLocation} onDecide={decideKost} busy={busy} />}
    {page === 'students' && <StudentsPage students={students} onCreate={createStudent} onUpdate={updateStudent} onDelete={deleteStudent} busy={busy} />}
    {page === 'inspection' && <InspectionPage students={students} onAnalyze={analyze} busy={busy} modelAvailable={model.status === 'ready'} modelMessage={model.message} />}
    {page === 'queueModules' && <QueueModulesPage onRun={runQueueDemo} busy={busy} />}
    {page === 'history' && <HistoryPage loadInspections={loadInspections} />}
    {page === 'settings' && <SettingsPage settings={settings} onSave={saveSettings} busy={busy} />}
  </Layout>;
}
