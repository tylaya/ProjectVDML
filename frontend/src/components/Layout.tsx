import { useState } from 'react';
import type { ReactNode } from 'react';
import { Building2, ClipboardCheck, History, LayoutDashboard, Menu, Settings as SettingsIcon, Users, X } from 'lucide-react';
import type { Page, Settings } from '../types';

const items: { id: Page; label: string; icon: typeof Users }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'students', label: 'Data Mahasiswa', icon: Users },
  { id: 'inspection', label: 'Pemeriksaan Kategori', icon: ClipboardCheck },
  { id: 'history', label: 'Riwayat Pemeriksaan', icon: History },
  { id: 'settings', label: 'Pengaturan', icon: SettingsIcon },
];

export function Layout({ page, onNavigate, settings, pending, children }: {
  page: Page; onNavigate: (page: Page) => void; settings: Settings; pending: number; children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const sidebar = <div className="flex h-full flex-col bg-royal text-white">
    <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5"><div className="rounded-xl bg-gold p-2.5 text-royal"><Building2 size={21} /></div><div><b className="block text-sm tracking-wide">VILLAGE DEAN</b><span className="text-xs text-yellow-100">Universitas Klabat</span></div></div>
    <nav className="flex-1 space-y-1 px-3 py-5"><p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-purple-200/70">Menu Utama</p>{items.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { onNavigate(id); setMenuOpen(false); }} className={`flex w-full items-center justify-between rounded-lg px-3 py-3 text-left text-sm ${page === id ? 'bg-gold font-semibold text-royal shadow-sm' : 'text-purple-50 hover:bg-white/10'}`}><span className="flex items-center gap-3"><Icon size={17} />{label}</span>{id === 'history' && pending > 0 && <span className="rounded-full bg-gold px-2 py-0.5 text-xs font-semibold text-royal">{pending}</span>}</button>)}</nav>
    <div className="border-t border-white/10 p-4"><div className="rounded-lg bg-white/5 p-3 text-xs"><b className="text-yellow-100">Sistem Verifikasi ML</b><p className="mt-1 leading-relaxed text-purple-100/75">Hasil merupakan dukungan administratif dan bukan keputusan final.</p></div></div>
  </div>;
  return <div className="flex min-h-screen bg-slate-50">
    <aside className="hidden w-64 shrink-0 lg:block">{sidebar}</aside>
    {menuOpen && <div className="fixed inset-0 z-50 flex lg:hidden"><button className="absolute inset-0 bg-slate-950/50" aria-label="Tutup menu" onClick={() => setMenuOpen(false)} /><aside className="relative w-72 shadow-xl">{sidebar}<button className="absolute right-3 top-4 p-2" onClick={() => setMenuOpen(false)} aria-label="Tutup"><X size={20} /></button></aside></div>}
    <div className="flex min-w-0 flex-1 flex-col"><header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-purple-900 bg-royal px-4 text-white shadow-sm sm:px-7"><div className="flex items-center gap-3"><button className="rounded-lg border border-white/20 p-2 text-white hover:bg-white/10 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Buka menu"><Menu size={18} /></button><div><h1 className="text-sm font-bold text-white sm:text-base">Village Dean – Housing Verification System</h1><p className="hidden text-xs text-purple-100 sm:block">Sistem Verifikasi Kategori Hunian Mahasiswa Universitas Klabat</p></div></div><div className="hidden text-right sm:block"><b className="block text-sm text-white">{settings.officer_name}</b><span className="text-xs text-purple-100">{settings.officer_title}</span></div></header><main className="w-full flex-1 p-4 sm:p-6 lg:p-8">{children}</main></div>
  </div>;
}
