import { useState } from 'react';
import type { FormEvent } from 'react';
import { Building2, ClipboardCheck, FileCheck2, LogOut, PlusCircle, ShieldCheck } from 'lucide-react';
import { GoogleMapsDirectionsLink } from '../components/GoogleMapsDirectionsLink';
import type { Application, ApplicationInput, AuthUser, Kost, RegistrationPeriod } from '../types';

const initialForm: ApplicationInput = {
  request_type: 'Pendaftaran baru',
  category: 'Outsider Dekat',
  residence_type: 'Keluarga',
  kost_id: null,
  semester: '',
  nama_mahasiswa: '',
  nama_kost: '',
  alamat_kost: '',
  maps_url: '',
  kelurahan: 'Airmadidi',
  jarak_km: 2,
  waktu_tempuh_menit: 10,
  akses_jalan: 'Jalan Utama',
};

const statusTone: Record<Application['status'], string> = {
  'Menunggu verifikasi': 'bg-amber-50 text-amber-800',
  'Perlu revisi': 'bg-orange-50 text-orange-800',
  'Disetujui': 'bg-emerald-50 text-emerald-800',
  'Ditolak': 'bg-rose-50 text-rose-800',
};

export function StudentPortalPage({ user, applications, kosts, registrationPeriod, onSubmit, onLogout, busy, error }: {
  user: AuthUser;
  applications: Application[];
  kosts: Pick<Kost, 'id' | 'name' | 'address' | 'maps_url' | 'kelurahan' | 'residence_type'>[];
  registrationPeriod: RegistrationPeriod;
  onSubmit: (application: ApplicationInput, ktp: File | null, kartuKeluarga: File | null, residenceProof: File | null) => Promise<void>;
  onLogout: () => void;
  busy: boolean;
  error: string;
}) {
  const [form, setForm] = useState(initialForm);
  const [notice, setNotice] = useState('');
  const [ktp, setKtp] = useState<File | null>(null);
  const [kartuKeluarga, setKartuKeluarga] = useState<File | null>(null);
  const [residenceProof, setResidenceProof] = useState<File | null>(null);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setNotice('');
    try {
      await onSubmit({ ...form, semester: registrationPeriod.semester_name }, ktp, kartuKeluarga, residenceProof);
      setNotice('Pengajuan tersimpan dan masuk ke antrean verifikasi petugas.');
      setForm(initialForm);
      setKtp(null);
      setKartuKeluarga(null);
      setResidenceProof(null);
    } catch {
      // The shared application shell displays the API error.
    }
  };
  const update = <K extends keyof ApplicationInput>(key: K, value: ApplicationInput[K]) =>
    setForm(current => ({ ...current, [key]: value }));

  return <main className="min-h-screen bg-slate-50">
    <header className="border-b border-slate-200 bg-white px-4 py-3.5 text-slate-800 shadow-sm sm:px-8"><div className="mx-auto flex max-w-6xl items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="rounded-xl bg-royal p-2.5 text-gold"><Building2 size={20} /></span><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-royal">SIGAP-VD</p><h1 className="text-sm font-semibold text-slate-600">Portal Mahasiswa</h1></div></div><div className="flex items-center gap-3"><span className="hidden text-right text-xs sm:block"><b className="block text-sm text-slate-800">{user.name}</b><span className="text-slate-500">{user.email}</span></span><button onClick={onLogout} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><LogOut size={15} />Keluar</button></div></div></header>
    <div className="mx-auto grid max-w-6xl gap-6 p-4 sm:p-8 lg:grid-cols-5">
      <section className="relative isolate overflow-hidden rounded-2xl bg-royal p-6 text-white shadow-lg shadow-slate-900/10 sm:p-8 lg:col-span-5">
        <div className="pointer-events-none absolute -right-10 -top-20 -z-10 h-56 w-56 rounded-full border-[30px] border-white/[0.05]" />
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-200">Layanan administrasi mahasiswa</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div><h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Pengajuan tempat tinggal</h2><p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-200">Lengkapi informasi hunian dan dokumen pendukung. Tim Village Dean akan meninjau pengajuan Anda.</p></div>
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-3 py-2 text-xs font-medium text-slate-200"><ShieldCheck size={15} className="text-emerald-300" /> Data dikirim secara aman</span>
        </div>
      </section>
      <section className="space-y-5 lg:col-span-3">
        <div><h2 className="text-lg font-bold text-slate-900">Informasi pengajuan</h2><p className="mt-1 text-sm text-slate-500">Isi seluruh kolom bertanda wajib. Keputusan akhir ditetapkan oleh petugas.</p></div>
        <div className="flex gap-3 rounded-2xl border border-blue-200 bg-blue-50/80 p-4 text-sm leading-relaxed text-blue-950"><FileCheck2 size={19} className="mt-0.5 shrink-0 text-blue-700" /><div><b>Siapkan dokumen pendukung</b><p className="mt-1 text-blue-900">Kost: bukti pendaftaran/terdaftar dari kost. Rumah: surat keterangan domisili RT/RW atau pemerintah setempat. Mahasiswa yang tinggal di rumah wajib mengunggah KTP dan Kartu Keluarga; Outsider Jauh juga wajib mengunggah keduanya. Format PDF/JPG/PNG, maksimal 5 MB per berkas.</p><p className="mt-1 text-xs font-medium text-blue-800">Jangan unggah dokumen pribadi sebelum kebijakan retensi dan penghapusan data ditetapkan.</p></div></div>
        {!registrationPeriod.configured ? <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Jadwal pendaftaran semester belum dikonfigurasi. Hubungi admin Village Dean.</p> : <p role="status" className={`rounded-lg p-3 text-sm ${registrationPeriod.is_open ? 'border border-emerald-200 bg-emerald-50 text-emerald-900' : 'border border-slate-200 bg-slate-100 text-slate-700'}`}>{registrationPeriod.is_open ? `Pendaftaran ${registrationPeriod.semester_name} dibuka sampai ${registrationPeriod.end_date} (WITA).` : `Pendaftaran ${registrationPeriod.semester_name} hanya dibuka ${registrationPeriod.start_date}–${registrationPeriod.end_date}. Untuk pembaruan data terdaftar, hubungi petugas Village Dean.`}</p>}
        {registrationPeriod.configured && !registrationPeriod.location_configured && <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Lokasi kampus belum dikonfigurasi. Admin perlu mengisi tautan Google Maps kampus sebelum pengajuan dapat dikirim.</p>}
        {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}
        <form onSubmit={submit} className="space-y-4 rounded-2xl border bg-white p-5 shadow-sm sm:p-6">
          <label className="block text-sm font-medium text-slate-700">Jenis pengajuan<select value={form.request_type} onChange={event => update('request_type', event.target.value as ApplicationInput['request_type'])} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option>Pendaftaran baru</option><option>Perpanjangan</option></select></label>
          <label className="block text-sm font-medium text-slate-700">Nama mahasiswa<input required maxLength={120} value={form.nama_mahasiswa} onChange={event => update('nama_mahasiswa', event.target.value)} placeholder="Nama lengkap" className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
          <label className="block text-sm font-medium text-slate-700">Tipe hunian<select value={form.residence_type} onChange={event => {
            const residence_type = event.target.value as ApplicationInput['residence_type'];
            setForm(current => ({ ...current, residence_type, kost_id: null, nama_kost: '', alamat_kost: '', maps_url: '', kelurahan: 'Airmadidi' }));
            setResidenceProof(null);
            if (form.category === 'Outsider Dekat' && (residence_type === 'Kost putra' || residence_type === 'Kost putri')) {
              setKtp(null);
              setKartuKeluarga(null);
            }
          }} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><optgroup label="Tinggal di rumah"><option value="Keluarga">Rumah bersama keluarga</option><option value="Wali">Rumah bersama wali</option></optgroup><optgroup label="Tinggal di kost"><option>Kost putra</option><option>Kost putri</option></optgroup></select></label>
          {form.residence_type === 'Kost putra' || form.residence_type === 'Kost putri' ? <>
            <label className="block text-sm font-medium text-slate-700">Kost yang sudah disetujui kampus<select required value={form.kost_id ?? ''} onChange={event => {
              const kost = kosts.find(item => item.id === Number(event.target.value));
              setForm(current => ({
                ...current,
                kost_id: kost?.id ?? null,
                nama_kost: kost?.name ?? '',
                alamat_kost: kost?.address ?? '',
                maps_url: kost?.maps_url ?? '',
                kelurahan: kost?.kelurahan ?? '',
              }));
            }} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option value="">Pilih kost terdaftar...</option>{kosts.filter(kost => kost.residence_type === form.residence_type).map(kost => <option key={kost.id} value={kost.id}>{kost.name} — {kost.kelurahan}</option>)}</select></label>
            {!kosts.some(kost => kost.residence_type === form.residence_type) && <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-600">Belum ada kost tipe ini yang disetujui kampus. Hubungi admin Village Dean.</p>}
            {form.kost_id && !form.maps_url && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Tautan lokasi kost belum diisi oleh admin. Hubungi Village Dean sebelum mendaftar.</p>}
            {form.kost_id && <div className="space-y-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-600"><p>{form.alamat_kost}, {form.kelurahan}</p><GoogleMapsDirectionsLink destination={[form.alamat_kost, form.kelurahan].filter(Boolean).join(', ')} /></div>}
          </> : <>
            <label className="block text-sm font-medium text-slate-700">Nama hunian / keluarga / wali<input required maxLength={120} value={form.nama_kost} onChange={event => update('nama_kost', event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
            <label className="block text-sm font-medium text-slate-700">Alamat domisili<input required maxLength={240} value={form.alamat_kost} onChange={event => update('alamat_kost', event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
            <label className="block text-sm font-medium text-slate-700">Tautan lokasi Google Maps<input required type="url" maxLength={2048} value={form.maps_url} onChange={event => update('maps_url', event.target.value)} placeholder="Tautan lengkap dengan koordinat lokasi rumah" className="mt-1 w-full rounded-lg border px-3 py-2.5" /><span className="mt-1 block text-xs font-normal text-slate-500">Jarak dihitung otomatis secara lokal; tautan pendek tidak didukung.</span></label>
            <label className="block text-sm font-medium text-slate-700">Kelurahan<input required maxLength={80} value={form.kelurahan} onChange={event => update('kelurahan', event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
          </>}
          <div className="grid gap-3 sm:grid-cols-2">
            <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">Jarak hunian dari kampus dihitung otomatis setelah tautan lokasi diperiksa.</p>
            <label className="block text-sm font-medium text-slate-700">Waktu tempuh (menit)<input required type="number" min="1" max="1440" value={form.waktu_tempuh_menit} onChange={event => update('waktu_tempuh_menit', Number(event.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
          </div>
          <label className="block text-sm font-medium text-slate-700">Akses jalan<select value={form.akses_jalan} onChange={event => update('akses_jalan', event.target.value as ApplicationInput['akses_jalan'])} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option>Jalan Utama</option><option>Lorong</option><option>Perbukitan</option></select></label>
          <label className="block text-sm font-medium text-slate-700">Kategori tempat tinggal<select value={form.category} onChange={event => {
            const category = event.target.value as ApplicationInput['category'];
            update('category', category);
            if (category === 'Outsider Dekat' && (form.residence_type === 'Kost putra' || form.residence_type === 'Kost putri')) {
              setKtp(null);
              setKartuKeluarga(null);
            }
          }} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5"><option>Outsider Dekat</option><option>Outsider Jauh</option></select></label>
          {(form.category === 'Outsider Jauh' || form.residence_type === 'Keluarga' || form.residence_type === 'Wali') && <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">Berkas KTP (wajib)<input required type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={event => setKtp(event.target.files?.[0] ?? null)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm" /></label>
            <label className="block text-sm font-medium text-slate-700">Berkas Kartu Keluarga (wajib)<input required type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={event => setKartuKeluarga(event.target.files?.[0] ?? null)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm" /></label>
          </div>}
          <label className="block text-sm font-medium text-slate-700">
            {form.residence_type === 'Kost putra' || form.residence_type === 'Kost putri' ? 'Surat bukti terdaftar / pendaftaran kost (wajib)' : 'Surat keterangan domisili RT/RW atau pemerintah setempat (wajib)'}
            <input required type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={event => setResidenceProof(event.target.files?.[0] ?? null)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm" />
          </label>
          <label className="block text-sm font-medium text-slate-700">Periode semester<input required readOnly value={registrationPeriod.semester_name} className="mt-1 w-full rounded-lg border bg-slate-50 px-3 py-2.5" /></label>
          <button disabled={busy || !registrationPeriod.is_open || !registrationPeriod.location_configured} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-royal px-4 py-3 text-sm font-semibold text-white shadow-md shadow-royal/10 hover:bg-slate-800 disabled:opacity-50"><PlusCircle size={17} />{busy ? 'Mengirim pengajuan…' : 'Kirim pengajuan'}</button>
        </form>
      </section>
      <section className="space-y-4 lg:col-span-2"><div><h2 className="text-lg font-bold text-slate-900">Status pengajuan</h2><p className="mt-1 text-sm text-slate-500">Perkembangan pengajuan yang terhubung dengan akun Anda.</p></div>
        {!applications.length ? <div className="rounded-2xl border bg-white p-8 text-center"><ClipboardCheck className="mx-auto text-slate-300" size={30} /><p className="mt-3 text-sm font-medium text-slate-700">Belum ada pengajuan</p><p className="mt-1 text-xs text-slate-500">Pengajuan yang dikirim akan muncul di sini.</p></div> : applications.map(application => <article key={application.id} className="rounded-2xl border bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-medium text-slate-500">Nomor pengajuan</p><h3 className="mt-1 font-bold text-royal">VD-{String(application.id).padStart(5, '0')}</h3></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone[application.status]}`}>{application.status}</span></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-slate-500">Tipe</dt><dd className="mt-1 font-medium">{application.request_type}</dd></div><div><dt className="text-xs text-slate-500">Kategori</dt><dd className="mt-1 font-medium">{application.category}</dd></div><div><dt className="text-xs text-slate-500">Hunian</dt><dd className="mt-1 font-medium">{application.residence_type}</dd></div><div><dt className="text-xs text-slate-500">Semester</dt><dd className="mt-1 font-medium">{application.semester}</dd></div>{application.kost_id && <div><dt className="text-xs text-slate-500">Konfirmasi kost</dt><dd className="mt-1 font-medium">{application.kost_confirmation_status}{application.kost_confirmation_note && ` — ${application.kost_confirmation_note}`}</dd></div>}</dl>{application.admin_note && <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600"><b>Catatan petugas:</b> {application.admin_note}</p>}<p className="mt-3 text-xs text-slate-400">Dikirim {new Date(application.created_at).toLocaleString('id-ID')}</p></article>)}
      </section>
    </div>
  </main>;
}
