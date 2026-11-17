import { useState } from 'react';
import type { FormEvent } from 'react';
import type { QueueModulesResult, QueueSimulationInput } from '../types';

function nextMonday(): string {
  const date = new Date();
  const daysUntilMonday = (8 - date.getDay()) % 7 || 7;
  date.setDate(date.getDate() + daysUntilMonday);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-bold text-royal">{value}</p></div>;
}

function ModuleCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="space-y-4 rounded-xl border bg-white p-5"><h3 className="font-semibold text-royal">{title}</h3>{children}</section>;
}

export function QueueModulesPage({ onRun, busy }: {
  onRun: (input: QueueSimulationInput) => Promise<QueueModulesResult>;
  busy: boolean;
}) {
  const [form, setForm] = useState<QueueSimulationInput>({
    start_date: nextMonday(),
    service_counters: 2,
    applicants_per_day: 80,
    seed: 42,
  });
  const [result, setResult] = useState<QueueModulesResult | null>(null);
  const [error, setError] = useState('');
  const startIsMonday = form.start_date !== '' && new Date(`${form.start_date}T12:00:00`).getDay() === 1;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      setResult(await onRun(form));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Simulasi gagal dijalankan.');
    }
  };

  const reset = () => {
    setResult(null);
    setError('');
    setForm({ start_date: nextMonday(), service_counters: 2, applicants_per_day: 80, seed: 42 });
  };

  return <div className="space-y-6">
    <header><h2 className="text-xl font-bold text-royal">Laboratorium Modul Antrean ML</h2><p className="mt-1 text-sm text-slate-500">Simulasi satu minggu pendaftaran awal semester, sebelum pembayaran dan kontrak mata kuliah.</p></header>
    <div role="note" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">
      <b>Mode simulasi saja.</b> Data seluruhnya sintetis. Tidak membuat slot, tiket, check-in, notifikasi, atau antrean nyata; tidak membaca/menyimpan data mahasiswa. Jam Senin–Jumat 08.00–17.00 mengikuti asumsi awal. Jumlah loket, volume, dokumen, serta aturan triase masih contoh dan perlu dikonfirmasi.
    </div>
    <form onSubmit={submit} className="grid gap-4 rounded-xl border bg-white p-5 sm:grid-cols-2 lg:grid-cols-5">
      <label className="text-xs font-medium text-slate-600">Senin, tanggal mulai
        <input required type="date" value={form.start_date} onChange={event => setForm(current => ({ ...current, start_date: event.target.value }))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" />
      </label>
      <label className="text-xs font-medium text-slate-600">Loket (asumsi)
        <input required type="number" min="1" max="10" value={form.service_counters} onChange={event => setForm(current => ({ ...current, service_counters: Number(event.target.value) }))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" />
      </label>
      <label className="text-xs font-medium text-slate-600">Pendaftar/hari (sintetis)
        <input required type="number" min="5" max="100" value={form.applicants_per_day} onChange={event => setForm(current => ({ ...current, applicants_per_day: Number(event.target.value) }))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" />
      </label>
      <label className="text-xs font-medium text-slate-600">Seed
        <input required type="number" min="0" max="999999" value={form.seed} onChange={event => setForm(current => ({ ...current, seed: Number(event.target.value) }))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" />
      </label>
      <div className="flex items-end gap-2"><button disabled={busy || !startIsMonday} className="flex-1 rounded-lg bg-royal px-4 py-2 text-sm font-semibold text-white hover:bg-violet-950 disabled:opacity-50">{busy ? 'Menghitung…' : 'Jalankan simulasi'}</button><button type="button" onClick={reset} className="rounded-lg border px-3 py-2 text-sm">Reset</button></div>
      {!startIsMonday && <p className="text-xs text-rose-700 sm:col-span-2 lg:col-span-5">Tanggal mulai simulasi harus hari Senin.</p>}
      {error && <p role="alert" className="text-sm text-rose-700 sm:col-span-2 lg:col-span-5">{error}</p>}
    </form>

    {!result ? <section className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">Jalankan simulasi untuk melihat hasil M1–M8.</section> : <>
      <p className="text-xs text-slate-500">Periode {result.period.start_date} sampai {result.period.end_date} · {result.period.hours} · {result.period.service_counters} loket · seed {result.seed}</p>
      <div className="grid gap-4 xl:grid-cols-2">
        <ModuleCard title="M1 · Prediksi durasi layanan">
          <div className="grid grid-cols-2 gap-3"><Stat label="MAE model (menit)" value={result.modules.M1.mae_minutes} /><Stat label="Baseline median (menit)" value={result.modules.M1.baseline_mae_minutes} /><Stat label="Estimasi rata-rata (menit)" value={result.modules.M1.mean_predicted_duration_minutes} /><Stat label="Sampel sintetis" value={result.modules.M1.sample_count} /></div>
          <p className="text-xs leading-relaxed text-slate-500">{result.modules.M1.model}. MAE diuji pada pembagian data sintetis, bukan data layanan kampus.</p>
        </ModuleCard>
        <ModuleCard title="M2 · Perkiraan beban pendaftaran">
          <p className="text-sm text-slate-600">Rata-rata prediksi: <b>{result.modules.M2.forecast_total}</b> pendaftar per minggu.</p>
          <div className="space-y-3">{result.modules.M2.forecast.map(day => <div key={day.weekday}><div className="mb-1 flex justify-between text-xs"><span>{day.weekday} · puncak {day.peak_hour}</span><b>{day.expected_applicants}/hari</b></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-royal" style={{ width: `${Math.min(100, day.expected_applicants / Math.max(1, ...result.modules.M2.forecast.map(item => item.expected_applicants)) * 100)}%` }} /></div></div>)}</div>
          <p className="text-xs leading-relaxed text-slate-500">{result.modules.M2.method}. Validasi sintetis: MAE harian {result.modules.M2.daily_mae_validation}, per jam {result.modules.M2.hourly_mae_validation} pendaftar. Angka bukan estimasi kampus.</p>
        </ModuleCard>
        <ModuleCard title="M3 · Prediksi no-show">
          <div className="grid grid-cols-2 gap-3"><Stat label="Probabilitas rata-rata" value={`${(result.modules.M3.predicted_no_show_rate * 100).toFixed(1)}%`} /><Stat label="No-show simulasi" value={result.modules.M3.simulated_no_shows} /><Stat label="Precision sintetis" value={result.modules.M3.precision} /><Stat label="Brier score sintetis" value={result.modules.M3.brier_score} /></div>
          <p className="text-xs text-slate-500">Prediksi tidak digunakan untuk overbooking atau membatasi hak memperoleh layanan.</p>
        </ModuleCard>
        <ModuleCard title="M4 · Triase kelengkapan/kategori">
          <div className="grid grid-cols-2 gap-3">{Object.entries(result.modules.M4.recommendations).map(([label, count]) => <Stat key={label} label={label} value={count} />)}</div>
          <p className="text-xs leading-relaxed text-slate-500">{result.modules.M4.note} Ambang contoh: {result.modules.M4.distance_threshold_km} km ± {result.modules.M4.review_zone_km} km.</p>
        </ModuleCard>
        <ModuleCard title="M5 · Checklist dokumen contoh">
          <div className="grid grid-cols-2 gap-3"><Stat label="Checklist lengkap" value={result.modules.M5.complete_count} /><Stat label="Belum lengkap" value={result.modules.M5.incomplete_count} /></div>
          <ul className="space-y-2 text-sm text-slate-600">{result.modules.M5.documents.map(document => <li key={document} className="flex justify-between gap-3"><span>{document}</span><span className="whitespace-nowrap text-xs">{result.modules.M5.document_checklist[document].provided} ada · {result.modules.M5.document_checklist[document].missing} kurang</span></li>)}</ul>
          <p className="text-xs text-slate-500">{result.modules.M5.note}</p>
        </ModuleCard>
        <ModuleCard title="M6 · Segmen layanan">
          <div className="grid grid-cols-2 gap-3">{Object.entries(result.modules.M6.segments).map(([label, count]) => <Stat key={label} label={label} value={count} />)}</div>
          <p className="text-xs text-slate-500">{result.modules.M6.note}</p>
        </ModuleCard>
        <ModuleCard title="M7 · Deteksi anomali sintetis">
          <div className="grid grid-cols-2 gap-3"><Stat label="Flag tinjauan" value={result.modules.M7.flagged_count} /><Stat label="Sampel" value={result.modules.M7.sample_count} /></div>
          {result.modules.M7.flags.length > 0 && <ul className="max-h-32 space-y-1 overflow-y-auto text-xs text-slate-600">{result.modules.M7.flags.map(flag => <li key={flag.id}><b>{flag.id}:</b> {flag.reasons.join(', ')}</li>)}</ul>}
          <p className="text-xs text-slate-500">{result.modules.M7.note}</p>
        </ModuleCard>
        <ModuleCard title="M8 · Perbandingan scheduler offline">
          <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-slate-500"><tr><th className="py-2 pr-3">Kebijakan</th><th className="py-2 pr-3">Rata-rata tunggu</th><th className="py-2 pr-3">P90 (maks. harian)</th><th className="py-2 pr-3">Tunggu maks.</th><th className="py-2">Selisih kategori</th></tr></thead><tbody className="divide-y">{Object.entries(result.modules.M8.policies).map(([key, policy]) => <tr key={key}><td className="py-2 pr-3 font-medium">{policy.label}</td><td className="py-2 pr-3">{policy.mean_wait_minutes} mnt</td><td className="py-2 pr-3">{policy.p90_wait_minutes} mnt</td><td className="py-2 pr-3">{policy.max_wait_minutes} mnt</td><td className="py-2">{policy.wait_gap_minutes} mnt</td></tr>)}</tbody></table></div>
          <p className="text-xs leading-relaxed text-slate-500">{result.modules.M8.note} Latihan Q-learning: {result.modules.M8.episodes} episode.</p>
        </ModuleCard>
      </div>
      <section className="overflow-hidden rounded-xl border bg-white"><div className="border-b px-5 py-4"><h3 className="font-semibold text-royal">Contoh hasil triase sintetis</h3></div><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-slate-500"><tr>{['ID demo', 'Kategori', 'Jarak', 'Checklist', 'Rekomendasi', 'Segmen'].map(label => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y">{result.applicant_samples.map(sample => <tr key={sample.id}><td className="px-4 py-3 font-semibold">{sample.id}</td><td className="px-4 py-3">{sample.category}</td><td className="px-4 py-3">{sample.distance_km} km</td><td className="px-4 py-3">{sample.documents_complete ? 'Contoh lengkap' : 'Contoh belum lengkap'}</td><td className="px-4 py-3">{sample.recommendation}</td><td className="px-4 py-3">{sample.segment}</td></tr>)}</tbody></table></div></section>
    </>}
  </div>;
}
