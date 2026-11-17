import { useState } from 'react';
import type { FormEvent } from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { CategoryBadge, StatusBadge } from '../components/StatusBadge';
import { HOME_ADDRESS_OPTION, HOME_NAME_OPTION, ResidenceField } from '../components/ResidenceField';
import type { Category, Inspection, InspectionInput, RoadAccess, Student } from '../types';

const empty: InspectionInput = { student_id: '', nama_mahasiswa: '', nama_kost: '', alamat_kost: '', kelurahan: 'Airmadidi Bawah', jarak_km: 1.5, waktu_tempuh_menit: 8, akses_jalan: 'Jalan Utama', kategori_terdaftar: 'Outsider Dekat' };
export function InspectionPage({ students, onAnalyze, busy, modelAvailable, modelMessage }: { students: Student[]; onAnalyze: (data: InspectionInput) => Promise<Inspection>; busy: boolean; modelAvailable: boolean; modelMessage?: string }) {
  const [form, setForm] = useState<InspectionInput>(empty);
  const [selectedStudent, setSelectedStudent] = useState('');
  const [result, setResult] = useState<Inspection | null>(null);
  const [error, setError] = useState('');
  const change = <K extends keyof InspectionInput>(key: K, value: InspectionInput[K]) => setForm(current => ({ ...current, [key]: value }));
  const choose = (id: string) => {
    const student = students.find(s => s.id === id);
    if (!student) { setForm(current => ({ ...current, student_id: id })); return; }
    setForm({ student_id: student.id, nama_mahasiswa: student.nama_mahasiswa, nama_kost: student.nama_kost, alamat_kost: student.alamat_kost, kelurahan: student.kelurahan, jarak_km: student.jarak_km, waktu_tempuh_menit: Math.max(3, Math.round(student.jarak_km * 5)), akses_jalan: 'Jalan Utama', kategori_terdaftar: student.kategori_terdaftar });
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('');
    try { setResult(await onAnalyze(form)); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Pemeriksaan gagal.'); }
  };
  const mismatch = result && result.kategori_terdaftar !== result.prediksi_kategori;
  const residenceNames = [...new Set([HOME_NAME_OPTION, ...students.map(student => student.nama_kost)])];
  const residenceAddresses = [...new Set([HOME_ADDRESS_OPTION, ...students.map(student => student.alamat_kost)])];
  return <div className="space-y-5">
    <div><h2 className="text-xl font-bold text-royal">Pemeriksaan Kategori Tempat Tinggal</h2><p className="mt-1 text-sm text-slate-500">Model memberikan rekomendasi administratif yang tetap memerlukan pertimbangan petugas.</p></div>
    <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 text-sm text-purple-950">Hasil prediksi merupakan dukungan verifikasi berdasarkan data yang dimasukkan, bukan keputusan final mengenai status mahasiswa.</div>
    {!modelAvailable && <div role="alert" className="rounded-xl border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900"><b>Analisis ML sementara tidak tersedia.</b><p className="mt-1">Data mahasiswa, dashboard, riwayat, dan pengaturan tetap dapat digunakan. Prediksi akan aktif kembali setelah model berhasil dimuat.</p>{modelMessage && <p className="mt-2 break-words text-xs">{modelMessage}</p>}</div>}
    <div className="grid gap-5 lg:grid-cols-5">
      <form onSubmit={submit} className="space-y-4 rounded-xl border bg-white p-5 lg:col-span-3"><div className="flex flex-wrap items-center justify-between gap-2 border-b pb-3"><h3 className="font-semibold text-royal">Data Pemeriksaan</h3><select value={selectedStudent} onChange={e => { setSelectedStudent(e.target.value); choose(e.target.value); }} className="max-w-60 rounded-lg border bg-white px-2 py-1.5 text-xs"><option value="">Isi dari data mahasiswa…</option>{students.map(s => <option key={s.id} value={s.id}>{s.id} — {s.nama_mahasiswa}</option>)}</select></div>
        {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="grid gap-3 sm:grid-cols-2">{([['student_id', 'ID (bukan NIM)'], ['nama_mahasiswa', 'Nama mahasiswa']] as const).map(([key, label]) => <label key={key} className="text-xs font-medium text-slate-600">{label}<input required value={form[key]} onChange={e => change(key, e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>)}
          <ResidenceField label="Nama kost / hunian" value={form.nama_kost} options={residenceNames} onChange={value => change('nama_kost', value)} />
          <ResidenceField label="Alamat kost / area domisili" value={form.alamat_kost} options={residenceAddresses} onChange={value => change('alamat_kost', value)} />
          <label className="text-xs font-medium text-slate-600">Kelurahan<input required value={form.kelurahan} onChange={e => change('kelurahan', e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-600">Jarak dari kampus (km)<input required type="number" min="0" step="0.1" value={form.jarak_km} onChange={e => change('jarak_km', Number(e.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-600">Waktu tempuh (menit)<input required type="number" min="1" value={form.waktu_tempuh_menit} onChange={e => change('waktu_tempuh_menit', Number(e.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-600">Akses jalan<select value={form.akses_jalan} onChange={e => change('akses_jalan', e.target.value as RoadAccess)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm"><option>Jalan Utama</option><option>Lorong</option><option>Perbukitan</option></select></label>
          <label className="text-xs font-medium text-slate-600">Kategori terdaftar<select value={form.kategori_terdaftar} onChange={e => change('kategori_terdaftar', e.target.value as Category)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm"><option>Outsider Dekat</option><option>Outsider Jauh</option></select></label>
        </div><div className="flex justify-end gap-2 border-t pt-4"><button type="button" onClick={() => { setForm(empty); setSelectedStudent(''); setResult(null); setError(''); }} className="rounded-lg border px-4 py-2 text-sm">Reset</button><button disabled={busy || !modelAvailable} className="rounded-lg bg-royal px-4 py-2 text-sm font-semibold text-white hover:bg-violet-950 disabled:opacity-50">{busy ? 'Menganalisis…' : modelAvailable ? 'Analisis & Simpan' : 'Analisis dinonaktifkan'}</button></div>
      </form>
      <section className="min-h-72 rounded-xl border bg-white p-5 lg:col-span-2"><h3 className="border-b pb-3 font-semibold text-royal">Hasil Analisis ML</h3>{!result ? <div className="flex h-56 items-center justify-center text-center text-sm text-slate-400">Lengkapi data untuk melihat rekomendasi model.</div> : <div className="mt-4 space-y-4">
        {mismatch && <div className="flex gap-2 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-xs leading-relaxed text-yellow-900"><AlertTriangle size={17} className="shrink-0" />Kategori prediksi berbeda dari data terdaftar. Mohon verifikasi administratif lebih lanjut.</div>}
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800"><CheckCircle2 size={16} />Hasil disimpan dalam riwayat SQLite.</div>
        <div className="space-y-3 rounded-lg bg-slate-50 p-4 text-sm"><div className="flex justify-between gap-2"><span className="text-slate-500">Prediksi model</span><CategoryBadge category={result.prediksi_kategori} /></div><div className="flex justify-between"><span className="text-slate-500">Kategori terdaftar</span><CategoryBadge category={result.kategori_terdaftar} /></div><div className="flex justify-between"><span className="text-slate-500">Confidence score</span><b>{(result.confidence_score * 100).toFixed(1)}%</b></div><div className="flex justify-between gap-2 border-t pt-3"><span className="text-slate-500">Status</span><StatusBadge status={result.status} /></div><p className="border-t pt-3 text-xs leading-relaxed text-slate-600">{result.keterangan}</p></div>
      </div>}</section>
    </div>
  </div>;
}
