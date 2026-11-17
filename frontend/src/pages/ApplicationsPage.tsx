import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { ClipboardList, Eye, X } from 'lucide-react';
import type { Application, ApplicationDecision } from '../types';

type DecisionStatus = ApplicationDecision['status'];
const decisions: DecisionStatus[] = ['Disetujui', 'Perlu revisi', 'Ditolak'];

export function ApplicationsPage({ applications, onDecide, busy }: {
  applications: Application[];
  onDecide: (id: number, decision: ApplicationDecision) => Promise<void>;
  busy: boolean;
}) {
  const [filter, setFilter] = useState('Semua');
  const [selected, setSelected] = useState<Application | null>(null);
  const [status, setStatus] = useState<DecisionStatus>('Disetujui');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const filtered = useMemo(() => filter === 'Semua' ? applications : applications.filter(item => item.status === filter), [applications, filter]);
  const openDecision = (application: Application) => {
    setSelected(application);
    setStatus(application.status === 'Perlu revisi' ? 'Perlu revisi' : 'Disetujui');
    setNote(application.admin_note);
    setError('');
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setError('');
    try {
      await onDecide(selected.id, { status, admin_note: note });
      setSelected(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Keputusan gagal disimpan.');
    }
  };

  return <div className="space-y-5">
    <div><h2 className="text-xl font-bold text-royal">Pengajuan Mahasiswa</h2><p className="mt-1 text-sm text-slate-500">Tinjau dan catat keputusan administratif. Model ML tidak menyetujui atau menolak pengajuan.</p></div>
    <div className="grid gap-3 sm:grid-cols-3">{[
      ['Menunggu verifikasi', applications.filter(item => item.status === 'Menunggu verifikasi').length],
      ['Perlu revisi', applications.filter(item => item.status === 'Perlu revisi').length],
      ['Selesai', applications.filter(item => item.status === 'Disetujui' || item.status === 'Ditolak').length],
    ].map(([label, count]) => <article key={label} className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold text-royal">{count}</p></article>)}</div>
    <section className="overflow-hidden rounded-xl border bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4"><div className="flex items-center gap-2 font-semibold text-royal"><ClipboardList size={18} />Daftar pengajuan</div><select value={filter} onChange={event => setFilter(event.target.value)} className="rounded-lg border bg-white px-3 py-2 text-sm"><option>Semua</option><option>Menunggu verifikasi</option><option>Perlu revisi</option><option>Disetujui</option><option>Ditolak</option></select></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['Mahasiswa (email kampus)', 'Pengajuan', 'Kategori', 'Hunian', 'Semester', 'Status', 'Diterima', 'Aksi'].map(title => <th key={title} className="whitespace-nowrap px-4 py-3">{title}</th>)}</tr></thead><tbody className="divide-y">{filtered.map(application => <tr key={application.id}><td className="whitespace-nowrap px-4 py-3 font-medium">{application.student_email}</td><td className="px-4 py-3">{application.request_type}</td><td className="px-4 py-3">{application.category}</td><td className="px-4 py-3">{application.residence_type}</td><td className="whitespace-nowrap px-4 py-3">{application.semester}</td><td className="whitespace-nowrap px-4 py-3"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs">{application.status}</span></td><td className="whitespace-nowrap px-4 py-3 text-xs">{new Date(application.created_at).toLocaleString('id-ID')}</td><td className="px-4 py-3"><button onClick={() => openDecision(application)} aria-label={`Tinjau pengajuan ${application.id}`} className="rounded-lg border p-2 text-royal hover:bg-slate-50"><Eye size={16} /></button></td></tr>)}{!filtered.length && <tr><td colSpan={8} className="p-10 text-center text-sm text-slate-400">Belum ada data pada filter ini.</td></tr>}</tbody></table></div>
    </section>
    {selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"><form onSubmit={submit} className="w-full max-w-lg space-y-4 rounded-2xl bg-white p-6 shadow-xl"><div className="flex items-start justify-between"><div><h3 className="font-bold text-royal">Tinjau pengajuan VD-{String(selected.id).padStart(5, '0')}</h3><p className="mt-1 text-xs text-slate-500">{selected.student_email}</p></div><button type="button" onClick={() => setSelected(null)} aria-label="Tutup"><X size={19} /></button></div><div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3 text-sm"><p><span className="block text-xs text-slate-500">Kategori</span>{selected.category}</p><p><span className="block text-xs text-slate-500">Hunian</span>{selected.residence_type}</p><p><span className="block text-xs text-slate-500">Jenis</span>{selected.request_type}</p><p><span className="block text-xs text-slate-500">Semester</span>{selected.semester}</p></div><label className="block text-sm font-medium">Keputusan<select value={status} onChange={event => setStatus(event.target.value as DecisionStatus)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5">{decisions.map(decision => <option key={decision}>{decision}</option>)}</select></label><label className="block text-sm font-medium">Catatan wajib<textarea required minLength={3} maxLength={500} value={note} onChange={event => setNote(event.target.value)} rows={3} className="mt-1 w-full rounded-lg border px-3 py-2" placeholder="Jelaskan hasil pemeriksaan atau perbaikan yang diperlukan." /></label>{error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<div className="flex justify-end gap-2 border-t pt-4"><button type="button" onClick={() => setSelected(null)} className="rounded-lg border px-4 py-2 text-sm">Batal</button><button disabled={busy} className="rounded-lg bg-royal px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Menyimpan…' : 'Simpan keputusan'}</button></div></form></div>}
  </div>;
}
