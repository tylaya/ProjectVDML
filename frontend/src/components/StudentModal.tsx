import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { X } from 'lucide-react';
import { HOME_ADDRESS_OPTION, HOME_NAME_OPTION, ResidenceField } from './ResidenceField';
import { GoogleMapsDirectionsLink } from './GoogleMapsDirectionsLink';
import type { Category, Student } from '../types';

type StudentFields = Omit<Student, 'id'> & { id: string };
const empty: StudentFields = { id: '', nama_mahasiswa: '', nama_kost: '', alamat_kost: '', maps_url: '', kelurahan: 'Airmadidi Bawah', jarak_km: 1, kategori_terdaftar: 'Outsider Dekat', location_anomaly: false };

export function StudentModal({ initial, students, onClose, onSave, busy }: {
  initial: Student | null; students: Student[]; onClose: () => void; onSave: (student: StudentFields) => Promise<void>; busy: boolean;
}) {
  const [form, setForm] = useState<StudentFields>(empty);
  const [error, setError] = useState('');
  useEffect(() => {
    setForm(initial ? { ...initial } : { ...empty, id: `VD-${Date.now().toString().slice(-6)}` });
    setError('');
  }, [initial]);
  const update = <K extends keyof StudentFields>(key: K, value: StudentFields[K]) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try { await onSave(form); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Data gagal disimpan.'); }
  };
  const residenceNames = [...new Set([HOME_NAME_OPTION, ...students.map(student => student.nama_kost)])];
  const residenceAddresses = [...new Set([HOME_ADDRESS_OPTION, ...students.map(student => student.alamat_kost)])];
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"><form onSubmit={submit} className="w-full max-w-xl space-y-4 rounded-2xl bg-white p-6 shadow-xl">
    <div className="flex items-center justify-between"><h3 className="font-bold text-royal">{initial ? 'Edit Data Mahasiswa' : 'Tambah Mahasiswa'}</h3><button type="button" onClick={onClose} aria-label="Tutup"><X size={19} /></button></div>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <div className="grid gap-3 sm:grid-cols-2">{([['id', 'ID (bukan NIM)'], ['nama_mahasiswa', 'Nama tampilan']] as const).map(([key, label]) => <label key={key} className="text-xs font-medium text-slate-600">{label}<input required value={form[key]} disabled={key === 'id' && Boolean(initial)} onChange={(e) => update(key, e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm disabled:bg-slate-100" /></label>)}
      <ResidenceField label="Nama kost / hunian" value={form.nama_kost} options={residenceNames} onChange={value => update('nama_kost', value)} />
      <ResidenceField label="Alamat kost / area domisili" value={form.alamat_kost} options={residenceAddresses} onChange={value => update('alamat_kost', value)} />
      <label className="text-xs font-medium text-slate-600 sm:col-span-2">Tautan lokasi Google Maps<input required type="url" maxLength={2048} value={form.maps_url} onChange={event => update('maps_url', event.target.value)} placeholder="Tautan lengkap yang memuat koordinat lokasi" className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>
      <div className="sm:col-span-2"><GoogleMapsDirectionsLink destination={[form.alamat_kost, form.kelurahan].filter(Boolean).join(', ')} /></div>
      <label className="text-xs font-medium text-slate-600">Kelurahan<input required value={form.kelurahan} onChange={(e) => update('kelurahan', e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></label>
      <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">Jarak diperbarui otomatis dari koordinat Maps saat data disimpan.</p>
      <label className="text-xs font-medium text-slate-600">Kategori terdaftar<select value={form.kategori_terdaftar} onChange={(e) => update('kategori_terdaftar', e.target.value as Category)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm"><option>Outsider Dekat</option><option>Outsider Jauh</option></select></label>
    </div>
    <div className="flex justify-end gap-2 border-t pt-4"><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">Batal</button><button disabled={busy} className="rounded-lg bg-royal px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Menyimpan…' : 'Simpan'}</button></div>
  </form></div>;
}
