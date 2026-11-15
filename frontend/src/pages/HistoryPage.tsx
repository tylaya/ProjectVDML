import { useEffect, useState } from 'react';
import { Download, Eye, Search, X } from 'lucide-react';
import { CategoryBadge, StatusBadge } from '../components/StatusBadge';
import type { Inspection, VerificationStatus } from '../types';

const statuses: VerificationStatus[] = ['Sesuai Kategori', 'Berpotensi Tidak Sesuai', 'Perlu Verifikasi Petugas'];
function csvEscape(value: string | number) { return `"${String(value).replace(/"/g, '""')}"`; }
export function HistoryPage({ loadInspections }: { loadInspections: (search: string, status: string) => Promise<Inspection[]> }) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [rows, setRows] = useState<Inspection[]>([]);
  const [selected, setSelected] = useState<Inspection | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = window.setTimeout(() => {
      loadInspections(query, status).then(data => { if (active) { setRows(data); setError(''); } })
        .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Riwayat gagal dimuat.'); })
        .finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [query, status, loadInspections]);
  const download = () => {
    const headers = ['ID Pemeriksaan', 'ID Mahasiswa', 'Nama', 'Kost', 'Kelurahan', 'Jarak km', 'Waktu menit', 'Akses jalan', 'Terdaftar', 'Prediksi', 'Confidence', 'Status', 'Tanggal'];
    const csv = [headers, ...rows.map(r => [r.id, r.student_id, r.nama_mahasiswa, r.nama_kost, r.kelurahan, r.jarak_km, r.waktu_tempuh_menit, r.akses_jalan, r.kategori_terdaftar, r.prediksi_kategori, r.confidence_score, r.status, r.tanggal_pemeriksaan])].map(row => row.map(csvEscape).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'riwayat-pemeriksaan-village-dean.csv'; link.click(); URL.revokeObjectURL(url);
  };
  return <div className="space-y-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-bold text-royal">Riwayat Pemeriksaan</h2><p className="mt-1 text-sm text-slate-500">Riwayat analisis yang tersimpan di SQLite.</p></div><button disabled={!rows.length} onClick={download} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm disabled:opacity-40"><Download size={16} />Unduh CSV</button></div>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <div className="flex flex-wrap gap-3 rounded-xl border bg-white p-4"><label className="relative min-w-56 flex-1"><Search size={16} className="absolute left-3 top-2.5 text-slate-400" /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Cari ID, nama, atau kost" className="w-full rounded-lg border py-2 pl-9 pr-3 text-sm" /></label><select value={status} onChange={e => setStatus(e.target.value)} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">Semua Status</option>{statuses.map(x => <option key={x}>{x}</option>)}</select></div>
    <section className="overflow-hidden rounded-xl border bg-white"><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['ID Mahasiswa', 'Nama Kost', 'Jarak', 'Terdaftar', 'Prediksi', 'Confidence', 'Status', 'Tanggal', 'Detail'].map(x => <th key={x} className="whitespace-nowrap px-4 py-3">{x}</th>)}</tr></thead><tbody className="divide-y">{rows.map(r => <tr key={r.id}><td className="whitespace-nowrap px-4 py-3 font-medium">{r.student_id}</td><td className="px-4 py-3">{r.nama_kost}</td><td className="whitespace-nowrap px-4 py-3">{r.jarak_km.toFixed(1)} km</td><td className="px-4 py-3"><CategoryBadge category={r.kategori_terdaftar} /></td><td className="px-4 py-3"><CategoryBadge category={r.prediksi_kategori} /></td><td className="px-4 py-3">{(r.confidence_score * 100).toFixed(1)}%</td><td className="px-4 py-3"><StatusBadge status={r.status} /></td><td className="whitespace-nowrap px-4 py-3 text-xs">{new Date(r.tanggal_pemeriksaan).toLocaleString('id-ID')}</td><td className="px-4 py-3"><button onClick={() => setSelected(r)} className="rounded border p-1.5" title="Lihat detail"><Eye size={16} /></button></td></tr>)}{!loading && !rows.length && <tr><td colSpan={9} className="p-8 text-center text-slate-400">Tidak ada riwayat yang cocok.</td></tr>}</tbody></table></div>{loading && <p className="p-4 text-center text-sm text-slate-400">Memuat riwayat…</p>}</section>
    {selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"><section className="w-full max-w-lg rounded-xl bg-white p-6"><div className="flex justify-between"><h3 className="font-bold text-royal">Detail Pemeriksaan #{selected.id}</h3><button onClick={() => setSelected(null)} aria-label="Tutup"><X size={19} /></button></div><div className="mt-4 grid grid-cols-2 gap-3 text-sm">{[['ID Mahasiswa', selected.student_id], ['Nama', selected.nama_mahasiswa], ['Kost', selected.nama_kost], ['Kelurahan', selected.kelurahan], ['Jarak', `${selected.jarak_km} km`], ['Waktu tempuh', `${selected.waktu_tempuh_menit} menit`], ['Akses jalan', selected.akses_jalan], ['Confidence', `${(selected.confidence_score * 100).toFixed(1)}%`]].map(([label, value]) => <div key={label}><p className="text-xs text-slate-500">{label}</p><p className="font-medium">{value}</p></div>)}</div><div className="mt-4 space-y-2"><p><CategoryBadge category={selected.kategori_terdaftar} /> <span className="mx-1 text-xs text-slate-400">→</span> <CategoryBadge category={selected.prediksi_kategori} /></p><StatusBadge status={selected.status} /><p className="rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600">{selected.keterangan}</p><p className="text-xs text-slate-400">{new Date(selected.tanggal_pemeriksaan).toLocaleString('id-ID')}</p></div></section></div>}
  </div>;
}
