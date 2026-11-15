import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Save } from 'lucide-react';
import type { Settings } from '../types';

export function SettingsPage({ settings, onSave, busy }: { settings: Settings; onSave: (settings: Settings) => Promise<void>; busy: boolean }) {
  const [form, setForm] = useState(settings);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  useEffect(() => setForm(settings), [settings]);
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => setForm(current => ({ ...current, [key]: value }));
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError(''); setNotice('');
    try { await onSave(form); setNotice('Pengaturan berhasil disimpan ke SQLite.'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Pengaturan gagal disimpan.'); }
  };
  return <div className="space-y-5"><div><h2 className="text-xl font-bold text-royal">Pengaturan Sistem</h2><p className="mt-1 text-sm text-slate-500">Kelola profil petugas serta ambang peninjauan rekomendasi model.</p></div>{notice && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}{error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <form onSubmit={submit} className="grid gap-5 lg:grid-cols-2"><section className="space-y-4 rounded-xl border bg-white p-5"><h3 className="border-b pb-3 font-semibold text-royal">Profil Petugas</h3>{([['officer_name', 'Nama tampilan'], ['officer_title', 'Jabatan'], ['officer_unit', 'Unit kerja']] as const).map(([key, label]) => <label key={key} className="block text-xs font-medium text-slate-600">{label}<input required value={form[key]} onChange={e => update(key, e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>)}</section>
      <section className="space-y-4 rounded-xl border bg-white p-5"><h3 className="border-b pb-3 font-semibold text-royal">Parameter Verifikasi</h3><label className="block text-xs font-medium text-slate-600">Confidence minimum ({Math.round(form.confidence_threshold * 100)}%)<input type="range" min="0.5" max="0.95" step="0.01" value={form.confidence_threshold} onChange={e => update('confidence_threshold', Number(e.target.value))} className="mt-3 w-full" /></label><label className="block text-xs font-medium text-slate-600">Ambang batas kategori (km)<input required type="number" min="0.1" step="0.1" value={form.distance_threshold_km} onChange={e => update('distance_threshold_km', Number(e.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label><label className="block text-xs font-medium text-slate-600">Zona verifikasi (± km)<input required type="number" min="0" step="0.05" value={form.verification_zone_km} onChange={e => update('verification_zone_km', Number(e.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.verification_zone_enabled} onChange={e => update('verification_zone_enabled', e.target.checked)} />Tandai lokasi dekat ambang untuk ditinjau</label><p className="text-xs leading-relaxed text-slate-500">Kasus dalam zona batas atau dengan confidence di bawah ambang akan diberi status Perlu Verifikasi Petugas.</p></section>
      <div className="flex justify-end lg:col-span-2"><button disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-royal px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-950 disabled:opacity-50"><Save size={16} />{busy ? 'Menyimpan…' : 'Simpan Pengaturan'}</button></div>
    </form>
  </div>;
}
