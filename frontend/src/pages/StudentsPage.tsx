import { useMemo, useState } from 'react';
import { Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { CategoryBadge } from '../components/StatusBadge';
import { StudentModal } from '../components/StudentModal';
import type { Category, Student } from '../types';

export function StudentsPage({ students, onCreate, onUpdate, onDelete, busy }: {
  students: Student[]; onCreate: (student: Omit<Student, 'id'> & { id: string }) => Promise<void>;
  onUpdate: (id: string, student: Omit<Student, 'id'>) => Promise<void>; onDelete: (id: string) => Promise<void>; busy: boolean;
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<'ALL' | Category>('ALL');
  const [editing, setEditing] = useState<Student | null | undefined>();
  const [error, setError] = useState('');
  const filtered = useMemo(() => students.filter(s => (category === 'ALL' || s.kategori_terdaftar === category) && `${s.id} ${s.nama_mahasiswa} ${s.nama_kost} ${s.kelurahan}`.toLowerCase().includes(query.toLowerCase())), [students, query, category]);
  const save = async (item: Omit<Student, 'id'> & { id: string }) => {
    if (editing) await onUpdate(editing.id, item); else await onCreate(item);
    setEditing(undefined);
  };
  const remove = async (s: Student) => {
    if (!window.confirm(`Hapus data ${s.nama_mahasiswa} (${s.id})? Riwayat pemeriksaan tetap tersimpan.`)) return;
    setError('');
    try { await onDelete(s.id); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Data gagal dihapus.'); }
  };
  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-bold text-royal">Data Mahasiswa</h2><p className="mt-1 text-sm text-slate-500">Data demonstrasi untuk pengelolaan dan pemeriksaan hunian.</p></div><button onClick={() => setEditing(null)} className="inline-flex items-center gap-2 rounded-lg bg-royal px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-950"><Plus size={16} />Tambah Data</button></div>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <section className="rounded-xl border bg-white p-4"><div className="flex flex-wrap gap-3"><label className="relative min-w-56 flex-1"><Search className="absolute left-3 top-2.5 text-slate-400" size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Cari ID, nama, kost, kelurahan" className="w-full rounded-lg border py-2 pl-9 pr-3 text-sm" /></label><select value={category} onChange={e => setCategory(e.target.value as 'ALL' | Category)} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="ALL">Semua kategori</option><option>Outsider Dekat</option><option>Outsider Jauh</option></select></div></section>
    <section className="overflow-hidden rounded-xl border bg-white"><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['ID', 'Nama Mahasiswa', 'Nama Kost', 'Kelurahan', 'Jarak', 'Kategori', 'Aksi'].map(x => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody className="divide-y">{filtered.map(s => <tr key={s.id}><td className="whitespace-nowrap px-4 py-3 font-semibold text-royal">{s.id}</td><td className="whitespace-nowrap px-4 py-3">{s.nama_mahasiswa}</td><td className="px-4 py-3">{s.nama_kost}</td><td className="px-4 py-3">{s.kelurahan}</td><td className="whitespace-nowrap px-4 py-3">{s.jarak_km.toFixed(1)} km</td><td className="px-4 py-3"><CategoryBadge category={s.kategori_terdaftar} /></td><td className="whitespace-nowrap px-4 py-3"><button title="Edit" onClick={() => setEditing(s)} className="mr-2 rounded border p-1.5 hover:bg-slate-50"><Pencil size={15} /></button><button title="Hapus" onClick={() => void remove(s)} className="rounded border border-rose-200 p-1.5 text-rose-600 hover:bg-rose-50"><Trash2 size={15} /></button></td></tr>)}{!filtered.length && <tr><td colSpan={7} className="p-8 text-center text-slate-400">Tidak ada data yang cocok.</td></tr>}</tbody></table></div></section>
    {editing !== undefined && <StudentModal initial={editing} onClose={() => setEditing(undefined)} onSave={save} busy={busy} />}
  </div>;
}
