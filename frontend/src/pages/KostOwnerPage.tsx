import { useState } from 'react';
import { Building2, CheckCircle2, ClipboardList, LogOut } from 'lucide-react';
import type { Application, AuthUser } from '../types';

export function KostOwnerPage({ user, applications, onConfirm, onLogout, busy, error }: {
  user: AuthUser;
  applications: Application[];
  onConfirm: (id: number, status: 'Dikonfirmasi' | 'Ditolak', note: string) => Promise<void>;
  onLogout: () => void;
  busy: boolean;
  error: string;
}) {
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [notice, setNotice] = useState('');
  const decide = async (id: number, status: 'Dikonfirmasi' | 'Ditolak') => {
    setNotice('');
    try {
      await onConfirm(id, status, notes[id] ?? '');
      setNotice('Konfirmasi penghuni berhasil disimpan.');
    } catch {
      // The shared application shell displays the API error.
    }
  };
  const pending = applications.filter(application => application.kost_confirmation_status === 'Menunggu kost').length;
  return <main className="min-h-screen bg-slate-50">
    <header className="border-b border-slate-200 bg-white px-4 py-3.5 text-slate-800 shadow-sm sm:px-8"><div className="mx-auto flex max-w-6xl items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="rounded-xl bg-royal p-2.5 text-gold"><Building2 size={20} /></span><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-royal">SIGAP-VD</p><h1 className="text-sm font-semibold text-slate-600">Portal Pemilik Kost</h1></div></div><div className="flex items-center gap-3"><span className="hidden text-right text-xs sm:block"><b className="block text-sm text-slate-800">{user.name}</b><span className="text-slate-500">{user.email}</span></span><button onClick={onLogout} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><LogOut size={15} />Keluar</button></div></div></header>
    <section className="mx-auto max-w-6xl space-y-5 p-4 sm:p-8">
      <div className="relative isolate overflow-hidden rounded-2xl bg-royal p-6 text-white shadow-lg shadow-slate-900/10 sm:p-8">
        <div className="pointer-events-none absolute -right-10 -top-20 -z-10 h-56 w-56 rounded-full border-[30px] border-white/[0.05]" />
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-200">Pengelolaan penghuni</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-5">
          <div><h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Konfirmasi penghuni kost</h2><p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-200">Tinjau mahasiswa yang mengajukan diri sebagai penghuni kost Anda. Keputusan akhir pengajuan tetap dilakukan pihak kampus.</p></div>
          <div className="flex items-center gap-3 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-3"><ClipboardList size={18} className="text-amber-200" /><div><p className="text-xl font-bold leading-none">{pending}</p><p className="mt-1 text-[10px] text-slate-300">Perlu dikonfirmasi</p></div></div>
        </div>
      </div>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}
      {!applications.length ? <div className="rounded-2xl border bg-white p-10 text-center shadow-sm"><CheckCircle2 className="mx-auto text-slate-300" size={32} /><p className="mt-3 text-sm font-semibold text-slate-700">Belum ada pengajuan penghuni</p><p className="mt-1 text-xs text-slate-500">Pengajuan yang masuk untuk kost Anda akan muncul di sini.</p></div> : <div className="grid gap-4 lg:grid-cols-2">{applications.map(application => <article key={application.id} className="rounded-2xl border bg-white p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-xs font-medium text-slate-500">Nomor pengajuan</p><h3 className="mt-1 font-bold text-royal">VD-{String(application.id).padStart(5, '0')}</h3></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{application.kost_confirmation_status}</span></div><div className="mt-4 border-t border-slate-100 pt-4"><p className="font-semibold text-slate-900">{application.nama_mahasiswa}</p><p className="mt-1 text-xs text-slate-500">{application.student_email}</p><p className="mt-3 text-sm text-slate-600">{application.nama_kost} · {application.semester}</p></div><label className="mt-4 block text-sm font-medium text-slate-700">Catatan <span className="font-normal text-slate-400">(opsional)</span><input maxLength={500} value={notes[application.id] ?? application.kost_confirmation_note} onChange={event => setNotes(current => ({ ...current, [application.id]: event.target.value }))} className="mt-1 w-full rounded-xl border px-3 py-2.5" placeholder="Catatan untuk kampus atau mahasiswa" /></label><div className="mt-4 flex flex-wrap gap-2"><button disabled={busy} onClick={() => void decide(application.id, 'Dikonfirmasi')} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"><CheckCircle2 size={16} />Konfirmasi penghuni</button><button disabled={busy} onClick={() => void decide(application.id, 'Ditolak')} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50">Tidak terdaftar</button></div></article>)}</div>}
    </section>
  </main>;
}
