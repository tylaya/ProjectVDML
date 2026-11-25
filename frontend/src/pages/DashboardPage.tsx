import { AlertCircle, ArrowRight, ClipboardCheck, Home, MapPin, Users } from 'lucide-react';
import { CategoryBadge, StatusBadge } from '../components/StatusBadge';
import type { Dashboard, ModelInfo, Page } from '../types';

export function DashboardPage({ data, model, navigate }: { data: Dashboard; model: ModelInfo; navigate: (page: Page) => void }) {
  const total = data.total_mahasiswa || 0;
  const cards = [
    { title: 'Total Mahasiswa', value: total, icon: Users, tone: 'bg-purple-50 text-purple-800' },
    { title: 'Outsider Dekat', value: data.outsider_dekat, icon: Home, tone: 'bg-yellow-50 text-yellow-900' },
    { title: 'Outsider Jauh', value: data.outsider_jauh, icon: MapPin, tone: 'bg-violet-50 text-violet-800' },
    { title: 'Total Pemeriksaan', value: data.total_pemeriksaan, icon: ClipboardCheck, tone: 'bg-emerald-50 text-emerald-700' },
    { title: 'Perlu Ditinjau', value: data.perlu_verifikasi, icon: AlertCircle, tone: 'bg-yellow-50 text-yellow-900' },
  ];
  const near = data.distribusi_kategori['Outsider Dekat'] ?? 0;
  const far = data.distribusi_kategori['Outsider Jauh'] ?? 0;
  return <div className="space-y-6">
    <section className="relative isolate overflow-hidden rounded-2xl bg-royal px-6 py-7 text-white shadow-xl shadow-slate-900/10 sm:px-8 sm:py-8">
      <div className="pointer-events-none absolute -right-10 -top-20 -z-10 h-64 w-64 rounded-full border-[34px] border-white/[0.05]" />
      <div className="pointer-events-none absolute right-40 top-20 -z-10 h-32 w-32 rounded-full bg-white/[0.04]" />
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-2xl">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-200">Pusat kendali Village Dean</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">Ringkasan verifikasi hunian</h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-200">Pantau data mahasiswa, pengajuan, dan pemeriksaan administratif dari satu tempat.</p>
        </div>
        <button onClick={() => navigate('inspection')} className="inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-bold text-royal shadow-lg shadow-slate-950/10 hover:bg-amber-300">Mulai pemeriksaan <ClipboardCheck size={16} /></button>
      </div>
    </section>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{cards.map(({ title, value, icon: Icon, tone }) => <article key={title} className="rounded-2xl border bg-white p-5"><div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold text-slate-500">{title}</p><span className={`rounded-xl p-2.5 ${tone}`}><Icon size={17} /></span></div><p className="mt-4 text-3xl font-bold tracking-tight text-slate-900">{value}</p><p className="mt-1 text-[11px] text-slate-400">Data sistem saat ini</p></article>)}</div>
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="rounded-xl border bg-white p-6 lg:col-span-2"><h3 className="font-semibold text-royal">Distribusi Kategori Terdaftar</h3><p className="mb-6 mt-1 text-xs text-slate-500">Ringkasan mahasiswa pada masing-masing kategori.</p>{[['Outsider Dekat', near, 'bg-gold'], ['Outsider Jauh', far, 'bg-royal']].map(([label, amount, tone]) => <div key={label} className="mb-5"><div className="mb-2 flex justify-between text-sm"><span>{label}</span><b>{amount} ({total ? Math.round(Number(amount) / total * 100) : 0}%)</b></div><div className="h-3 overflow-hidden rounded-full bg-slate-100"><div className={`h-full ${tone}`} style={{ width: `${total ? Number(amount) / total * 100 : 0}%` }} /></div></div>)}<div className={`mt-8 rounded-xl border p-4 ${model.status === 'ready' ? 'border-purple-200 bg-purple-50' : 'border-yellow-300 bg-yellow-50'}`}><p className="text-xs font-semibold uppercase tracking-wide text-purple-800">{model.status === 'ready' ? 'Model Machine Learning Aktif' : 'Model Machine Learning Tidak Tersedia'}</p><p className="mt-1 font-semibold text-royal">{model.model_name}</p>{model.metrics ? <p className="mt-1 text-sm text-slate-600">Akurasi evaluasi: <b>{(model.metrics.accuracy * 100).toFixed(1)}%</b></p> : <p className="mt-1 text-sm text-yellow-900">Fitur analisis ML dinonaktifkan sampai model berhasil dimuat.</p>}<p className="mt-1 text-xs text-slate-500">Fitur: {model.features.join(', ')}</p>{model.message && <p className="mt-2 break-words text-xs text-rose-700">{model.message}</p>}</div></section>
      <section className="rounded-xl border bg-white p-6"><h3 className="font-semibold text-royal">Ringkasan Status</h3><div className="mt-5 space-y-3">{Object.entries(data.distribusi_status).map(([status, value]) => <div key={status} className="flex items-center justify-between gap-2 rounded-lg border p-3"><StatusBadge status={status as keyof typeof data.distribusi_status} /><b className="text-royal">{value}</b></div>)}</div><button onClick={() => navigate('history')} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold text-royal hover:bg-slate-50">Lihat riwayat <ArrowRight size={15} /></button></section>
    </div>
    <section className="overflow-hidden rounded-xl border bg-white"><div className="border-b px-5 py-4"><h3 className="font-semibold text-royal">Pemeriksaan Terbaru</h3></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['ID Mahasiswa', 'Mahasiswa', 'Jarak', 'Kategori Terdaftar', 'Status'].map(x => <th key={x} className="px-5 py-3">{x}</th>)}</tr></thead><tbody className="divide-y">{data.pemeriksaan_terbaru.map(item => <tr key={item.id}><td className="px-5 py-3 font-medium">{item.student_id}</td><td className="px-5 py-3">{item.nama_mahasiswa}</td><td className="px-5 py-3">{item.jarak_km.toFixed(1)} km</td><td className="px-5 py-3"><CategoryBadge category={item.kategori_terdaftar} /></td><td className="px-5 py-3"><StatusBadge status={item.status} /></td></tr>)}{!data.pemeriksaan_terbaru.length && <tr><td colSpan={5} className="p-8 text-center text-slate-400">Belum ada pemeriksaan.</td></tr>}</tbody></table></div></section>
  </div>;
}
