import { useState } from 'react';
import type { FormEvent } from 'react';
import type { Kost } from '../types';

const initialForm = {
  name: '',
  address: '',
  maps_url: '',
  kelurahan: '',
  residence_type: 'Kost putra' as Kost['residence_type'],
  owner_email: '',
};

export function KostsPage({ kosts, onCreate, onUpdateLocation, onDecide, busy }: {
  kosts: Kost[];
  onCreate: (input: typeof initialForm) => Promise<void>;
  onUpdateLocation: (id: number, mapsUrl: string) => Promise<void>;
  onDecide: (id: number, status: 'Disetujui' | 'Ditolak') => Promise<void>;
  busy: boolean;
}) {
  const [form, setForm] = useState(initialForm);
  const [locationInputs, setLocationInputs] = useState<Record<number, string>>({});
  const [error, setError] = useState('');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      await onCreate(form);
      setForm(initialForm);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Kost gagal didaftarkan.');
    }
  };
  const decide = async (id: number, status: 'Disetujui' | 'Ditolak') => {
    setError('');
    try {
      await onDecide(id, status);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Status kost gagal diperbarui.');
    }
  };
  const updateLocation = async (id: number) => {
    setError('');
    try {
      await onUpdateLocation(id, locationInputs[id] ?? kosts.find(kost => kost.id === id)?.maps_url ?? '');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Tautan lokasi kost gagal diperbarui.');
    }
  };

  return <div className="space-y-5">
    <div><h2 className="text-xl font-bold text-royal">Kost Terdaftar dan Approval Kampus</h2><p className="mt-1 text-sm text-slate-500">Masukkan kost dan akun Google pemiliknya. Mahasiswa hanya dapat memilih kost berstatus Disetujui.</p></div>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <form onSubmit={submit} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-2">
      <label className="text-sm font-medium">Nama kost<input required maxLength={120} value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
      <label className="text-sm font-medium">Jenis kost<select value={form.residence_type} onChange={event => setForm(current => ({ ...current, residence_type: event.target.value as Kost['residence_type'] }))} className="mt-1 w-full rounded-lg border bg-white px-3 py-2"><option>Kost putra</option><option>Kost putri</option></select></label>
      <label className="text-sm font-medium">Alamat kost<input required maxLength={240} value={form.address} onChange={event => setForm(current => ({ ...current, address: event.target.value }))} className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
      <label className="text-sm font-medium">Kelurahan<input required maxLength={80} value={form.kelurahan} onChange={event => setForm(current => ({ ...current, kelurahan: event.target.value }))} className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
      <label className="text-sm font-medium sm:col-span-2">Tautan lokasi Google Maps<input required type="url" maxLength={2048} value={form.maps_url} onChange={event => setForm(current => ({ ...current, maps_url: event.target.value }))} placeholder="Tautan lengkap yang memuat koordinat lokasi" className="mt-1 w-full rounded-lg border px-3 py-2" /><span className="mt-1 block text-xs font-normal text-slate-500">Jarak lokasi dihitung otomatis dari koordinat di tautan.</span></label>
      <label className="text-sm font-medium sm:col-span-2">Email Google pemilik kost<input required type="email" maxLength={254} value={form.owner_email} onChange={event => setForm(current => ({ ...current, owner_email: event.target.value }))} className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
      <button disabled={busy} className="rounded-lg bg-royal px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2">{busy ? 'Menyimpan…' : 'Daftarkan untuk approval'}</button>
    </form>
    <section className="overflow-x-auto rounded-xl border bg-white">
      <table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['Kost', 'Pemilik', 'Jenis', 'Status', 'Aksi'].map(item => <th key={item} className="whitespace-nowrap px-4 py-3">{item}</th>)}</tr></thead><tbody className="divide-y">
        {kosts.map(kost => <tr key={kost.id}><td className="px-4 py-3"><b>{kost.name}</b><span className="block text-xs text-slate-500">{kost.address}, {kost.kelurahan}</span>{kost.location_anomaly && <span className="mt-1 block text-xs font-semibold text-rose-700">Di luar Sulawesi Utara · perlu tinjau lokasi</span>}{kost.maps_url && <a className="mt-1 block text-xs text-blue-700 underline" href={kost.maps_url} target="_blank" rel="noopener noreferrer">Titik lokasi</a>}<label className="mt-2 block text-xs font-medium text-slate-600">Perbarui tautan Maps<input type="url" maxLength={2048} value={locationInputs[kost.id] ?? kost.maps_url} onChange={event => setLocationInputs(current => ({ ...current, [kost.id]: event.target.value }))} placeholder="Tautan lengkap dengan koordinat" className="mt-1 w-full min-w-64 rounded border px-2 py-1.5" /></label><button disabled={busy || !(locationInputs[kost.id] ?? kost.maps_url)} onClick={() => void updateLocation(kost.id)} className="mt-1 rounded border px-2 py-1 text-xs text-royal disabled:opacity-50">Simpan lokasi</button></td><td className="px-4 py-3">{kost.owner_email}</td><td className="px-4 py-3">{kost.residence_type}</td><td className="px-4 py-3">{kost.approval_status}</td><td className="whitespace-nowrap px-4 py-3">{kost.approval_status !== 'Disetujui' && <button disabled={busy || Boolean(kost.location_anomaly)} onClick={() => void decide(kost.id, 'Disetujui')} className="mr-2 rounded border border-emerald-200 px-3 py-1.5 text-emerald-800 disabled:opacity-50">Setujui</button>}{kost.approval_status !== 'Ditolak' && <button disabled={busy} onClick={() => void decide(kost.id, 'Ditolak')} className="rounded border border-rose-200 px-3 py-1.5 text-rose-700 disabled:opacity-50">Tolak</button>}</td></tr>)}
        {!kosts.length && <tr><td colSpan={5} className="p-8 text-center text-slate-400">Belum ada data kost.</td></tr>}
      </tbody></table>
    </section>
  </div>;
}
