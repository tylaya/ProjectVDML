import { AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import type { Category, VerificationStatus } from '../types';

export function StatusBadge({ status }: { status: VerificationStatus }) {
  const styles: Record<VerificationStatus, string> = {
    'Sesuai Kategori': 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    'Berpotensi Tidak Sesuai': 'bg-rose-50 text-rose-700 ring-rose-200',
    'Perlu Verifikasi Petugas': 'bg-yellow-50 text-yellow-900 ring-yellow-300',
  };
  const Icon = status === 'Sesuai Kategori' ? CheckCircle2 : status === 'Perlu Verifikasi Petugas' ? Clock : AlertTriangle;
  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${styles[status]}`}><Icon size={14} />{status}</span>;
}

export function CategoryBadge({ category }: { category: Category }) {
  return <span className={`inline-flex whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium ${category === 'Outsider Dekat' ? 'bg-yellow-100 text-yellow-900' : 'bg-purple-100 text-purple-900'}`}>{category}</span>;
}
