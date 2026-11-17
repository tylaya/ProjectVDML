import { useState } from 'react';
import type { FormEvent } from 'react';
import { ClipboardCheck, LogOut, PlusCircle } from 'lucide-react';
import type { Application, ApplicationInput, AuthUser } from '../types';

const initialForm: ApplicationInput = {
  request_type: 'Pendaftaran baru',
  category: 'Outsider Dekat',
  residence_type: 'Keluarga',
  semester: '2026/2027 - Ganjil',
};

const statusTone: Record<Application['status'], string> = {
  'Menunggu verifikasi': 'bg-amber-50 text-amber-800',
  'Perlu revisi': 'bg-orange-50 text-orange-800',
  'Disetujui': 'bg-emerald-50 text-emerald-800',
  'Ditolak': 'bg-rose-50 text-rose-800',
};

export function StudentPortalPage({ user, applications, onSubmit, onLogout, busy, error }: {
  user: AuthUser;
  applications: Application[];
  onSubmit: (application: ApplicationInput) => Promise<void>;
  onLogout: () => void;
  busy: boolean;
  error: string;
}) {
  const [form, setForm] = useState(initialForm);
  const [notice, setNotice] = useState('');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setNotice('');
    try {
      await onSubmit(form);
      setNotice('Pengajuan tersimpan dan masuk ke antrean verifikasi petugas.');
      setForm(initialForm);
    } catch {
      // The shared application shell displays the API error.
    }
  };
  const update = <K extends keyof ApplicationInput>(key: K, value: ApplicationInput[K]) =>
    setForm(current => ({ ...current, [key]: value }));

  return <main className="min-h-screen bg-slate-50">
    <header className="bg-royal px-4 py-4 text-white sm:px-8"><div className="mx-auto flex max-w-6xl items-center justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-yellow-100">SIGAP-VD · Portal Mahasiswa</p><h1 className="mt-1 text-lg font-bold">Pendaftaran Tempat Tinggal Outsider</h1></div><div className="flex items-center gap-3"><span className="hidden text-right text-xs sm:block"><b className="block text-sm">{user.name}</b>{user.email}</span><button onClick={onLogout} className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-xs hover:bg-white/10"><LogOut size={15} />Keluar</button></div></div></header>
    <div className="mx-auto grid max-w-6xl gap-6 p-4 sm:p-8 lg:grid-cols-5">
      <section className="space-y-5 lg:col-span-3">
        <div><h2 className="text-xl font-bold text-royal">Ajukan pendaftaran</h2><p className="mt-1 text-sm text-slate-500">Isi data dasar berikut. Petugas Village Dean tetap melakukan pemeriksaan dan mengambil keputusan akhir.</p></div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950"><b>Catatan prototipe</b><p className="mt-1">Pengunggahan surat domisili, alamat lengkap, dan penjadwalan slot belum tersedia. Jangan masukkan data pribadi sensitif pada tahap demo ini.</p></div>
        {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}
        <form onSubmit={submit} className="space-y-4 rounded-xl border bg-white p-5">
          <label className="block text-sm font-medium text-slate-700">Jenis pengajuan<select value={form.request_type} onChange={event => update('request_type', event.target.value as ApplicationInput['request_type'])} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option>Pendaftaran baru</option><option>Perpanjangan</option></select></label>
          <label className="block text-sm font-medium text-slate-700">Kategori tempat tinggal<select value={form.category} onChange={event => update('category', event.target.value as ApplicationInput['category'])} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option>Outsider Dekat</option><option>Outsider Jauh</option></select></label>
          <label className="block text-sm font-medium text-slate-700">Tipe hunian<select value={form.residence_type} onChange={event => update('residence_type', event.target.value as ApplicationInput['residence_type'])} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option>Keluarga</option><option>Wali</option><option>Kost putra</option><option>Kost putri</option></select></label>
          <label className="block text-sm font-medium text-slate-700">Periode semester<input required maxLength={40} value={form.semester} onChange={event => update('semester', event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
          <button disabled={busy} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-royal px-4 py-3 text-sm font-semibold text-white hover:bg-violet-950 disabled:opacity-50"><PlusCircle size={17} />{busy ? 'Mengirim pengajuan…' : 'Kirim pengajuan'}</button>
        </form>
      </section>
      <section className="space-y-4 lg:col-span-2"><div><h2 className="text-xl font-bold text-royal">Status pengajuan</h2><p className="mt-1 text-sm text-slate-500">Hanya pengajuan milik akun Anda yang ditampilkan.</p></div>
        {!applications.length ? <div className="rounded-xl border bg-white p-8 text-center"><ClipboardCheck className="mx-auto text-slate-300" size={30} /><p className="mt-3 text-sm text-slate-500">Belum ada pengajuan untuk akun ini.</p></div> : applications.map(application => <article key={application.id} className="rounded-xl border bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs text-slate-500">Nomor pengajuan</p><h3 className="font-bold text-royal">VD-{String(application.id).padStart(5, '0')}</h3></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone[application.status]}`}>{application.status}</span></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-slate-500">Tipe</dt><dd className="mt-1 font-medium">{application.request_type}</dd></div><div><dt className="text-xs text-slate-500">Kategori</dt><dd className="mt-1 font-medium">{application.category}</dd></div><div><dt className="text-xs text-slate-500">Hunian</dt><dd className="mt-1 font-medium">{application.residence_type}</dd></div><div><dt className="text-xs text-slate-500">Semester</dt><dd className="mt-1 font-medium">{application.semester}</dd></div></dl>{application.admin_note && <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600"><b>Catatan petugas:</b> {application.admin_note}</p>}<p className="mt-3 text-xs text-slate-400">Dikirim {new Date(application.created_at).toLocaleString('id-ID')}</p></article>)}
      </section>
    </div>
  </main>;
}
