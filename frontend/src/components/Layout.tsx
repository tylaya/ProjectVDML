import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  Building2,
  ChevronRight,
  ClipboardCheck,
  History,
  House,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings as SettingsIcon,
  Users,
  X,
} from 'lucide-react';
import type { Page, Settings } from '../types';

const items: { id: Page; label: string; icon: typeof Users }[] = [
  { id: 'dashboard', label: 'Ringkasan', icon: LayoutDashboard },
  { id: 'applications', label: 'Pengajuan mahasiswa', icon: ClipboardCheck },
  { id: 'kosts', label: 'Data dan approval kost', icon: House },
  { id: 'students', label: 'Data mahasiswa', icon: Users },
  { id: 'inspection', label: 'Pemeriksaan hunian', icon: ClipboardCheck },
  { id: 'history', label: 'Riwayat pemeriksaan', icon: History },
  { id: 'queueModules', label: 'Laboratorium ML', icon: Activity },
  { id: 'settings', label: 'Pengaturan', icon: SettingsIcon },
];

const titles: Record<Page, string> = {
  dashboard: 'Ringkasan',
  applications: 'Pengajuan mahasiswa',
  kosts: 'Data dan approval kost',
  students: 'Data mahasiswa',
  inspection: 'Pemeriksaan hunian',
  history: 'Riwayat pemeriksaan',
  queueModules: 'Laboratorium modul ML',
  settings: 'Pengaturan sistem',
};

export function Layout({ page, onNavigate, settings, pending, onLogout, children }: {
  page: Page;
  onNavigate: (page: Page) => void;
  settings: Settings;
  pending: number;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const initials = settings.officer_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join('');

  const sidebar = (
    <div className="flex h-full flex-col bg-royal text-white">
      <div className="flex items-center gap-3 border-b border-white/10 px-6 py-6">
        <div className="rounded-xl bg-white/10 p-2.5 text-gold ring-1 ring-white/10">
          <Building2 size={22} />
        </div>
        <div>
          <b className="block text-sm font-bold tracking-[0.12em]">SIGAP-VD</b>
          <span className="mt-0.5 block text-[11px] text-slate-300">Village Dean · UNKLAB</span>
        </div>
      </div>
      <div className="px-5 pb-2 pt-6 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
        Workspace
      </div>
      <nav aria-label="Navigasi utama" className="flex-1 space-y-1 px-3 py-2">
        {items.map(({ id, label, icon: Icon }) => {
          const active = page === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => { onNavigate(id); setMenuOpen(false); }}
              aria-current={active ? 'page' : undefined}
              className={`group flex w-full items-center justify-between rounded-xl px-3 py-3 text-left text-[13px] transition ${
                active
                  ? 'bg-white text-royal shadow-lg shadow-slate-950/10'
                  : 'text-slate-300 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span className="flex min-w-0 items-center gap-3">
                <Icon size={17} className={active ? 'text-royal' : 'text-slate-400 group-hover:text-white'} />
                <span className="truncate">{label}</span>
              </span>
              {id === 'applications' && pending > 0
                ? <span className={`ml-2 min-w-6 rounded-full px-2 py-0.5 text-center text-[11px] font-bold ${active ? 'bg-royal text-white' : 'bg-amber-300 text-slate-900'}`}>{pending}</span>
                : active && <ChevronRight size={15} className="shrink-0 text-royal/60" />}
            </button>
          );
        })}
      </nav>
      <div className="m-4 rounded-xl border border-white/10 bg-white/[0.06] p-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-100">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          Verifikasi berbantuan ML
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
          Hasil model adalah rekomendasi. Keputusan administratif tetap di tangan petugas.
        </p>
      </div>
      <div className="border-t border-white/10 px-5 py-4 text-[10px] tracking-wide text-slate-400">
        UNIVERSITAS KLABAT · SIGAP-VD
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 lg:flex">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] lg:block">{sidebar}</aside>
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <button className="absolute inset-0 bg-slate-950/55 backdrop-blur-[2px]" aria-label="Tutup menu" onClick={() => setMenuOpen(false)} />
          <aside className="relative w-[284px] shadow-2xl">{sidebar}<button className="absolute right-3 top-4 rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => setMenuOpen(false)} aria-label="Tutup"><X size={19} /></button></aside>
        </div>
      )}
      <div className="min-w-0 flex-1 lg:ml-[264px]">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
          <div className="flex min-h-[76px] items-center justify-between gap-4 px-4 sm:px-7 lg:px-9">
            <div className="flex min-w-0 items-center gap-3">
              <button className="rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:bg-slate-50 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Buka menu"><Menu size={18} /></button>
              <div className="min-w-0">
                <p className="hidden text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 sm:block">Village Dean · Sistem Verifikasi Hunian</p>
                <h1 className="truncate text-base font-bold tracking-tight text-slate-900 sm:mt-1 sm:text-lg">{titles[page]}</h1>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <div className="hidden text-right md:block">
                <b className="block text-xs font-semibold text-slate-800">{settings.officer_name}</b>
                <span className="text-[11px] text-slate-500">{settings.officer_title}</span>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-royal ring-1 ring-slate-200" aria-label={`Petugas ${settings.officer_name}`}>{initials || 'VD'}</div>
              <button onClick={onLogout} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"><LogOut size={15} /><span className="hidden sm:inline">Keluar</span></button>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1680px] p-4 sm:p-6 lg:p-9">{children}</main>
      </div>
    </div>
  );
}
