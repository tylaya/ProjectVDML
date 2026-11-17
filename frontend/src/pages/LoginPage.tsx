import { useEffect, useRef, useState } from 'react';
import { Building2 } from 'lucide-react';
import type { LoginRole } from '../types';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (element: HTMLElement, options: { theme: string; size: string; shape: string; width: number }) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export function LoginPage({ onLogin }: {
  onLogin: (credential: string, email: string, role: LoginRole) => Promise<void>;
}) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const onLoginRef = useRef(onLogin);
  const emailRef = useRef('');
  const roleRef = useRef<LoginRole | ''>('');
  const googleInitialized = useRef(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<LoginRole | ''>('');
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const emailReady = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const canContinue = emailReady && Boolean(role);

  useEffect(() => { onLoginRef.current = onLogin; }, [onLogin]);
  useEffect(() => { emailRef.current = email.trim().toLowerCase(); }, [email]);
  useEffect(() => { roleRef.current = role; }, [role]);
  useEffect(() => {
    if (!clientId) return;
    const initializeGoogle = () => {
      if (!window.google || googleInitialized.current) return false;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: response => {
          setBusy(true);
          setError('');
          if (!emailRef.current || !roleRef.current) {
            setError('Masukkan email dan pilih peran terlebih dahulu.');
            setBusy(false);
            return;
          }
          void onLoginRef.current(response.credential, emailRef.current, roleRef.current).catch(reason => {
            setError(reason instanceof Error ? reason.message : 'Login Google gagal.');
          }).finally(() => setBusy(false));
        },
      });
      googleInitialized.current = true;
      setGoogleReady(true);
      return true;
    };
    if (initializeGoogle()) return;
    const script = document.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
    script?.addEventListener('load', initializeGoogle);
    return () => script?.removeEventListener('load', initializeGoogle);
  }, [clientId]);

  useEffect(() => {
    if (!buttonRef.current) return;
    buttonRef.current.replaceChildren();
    if (!googleReady || !canContinue || !window.google) return;
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: 'outline', size: 'large', shape: 'rectangular', width: 320,
    });
  }, [canContinue, googleReady]);

  const startLogin = () => {
    setError('');
    if (!canContinue) {
      setError('Masukkan email dan pilih peran terlebih dahulu.');
      return;
    }
    if (!window.google) {
      setError('Google belum siap. Coba tombol Sign in with Google di bawah.');
      return;
    }
    window.google.accounts.id.prompt();
  };

  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
    <section className="w-full max-w-md overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div className="bg-royal px-7 py-8 text-white"><div className="mb-5 inline-flex rounded-xl bg-gold p-3 text-royal"><Building2 size={24} /></div><h1 className="text-xl font-bold">SIGAP-VD</h1><p className="mt-1 text-sm text-purple-100">Portal Village Dean · Universitas Klabat</p></div>
      <div className="space-y-5 p-7"><div><h2 className="font-semibold text-slate-900">Masuk dengan akun kampus</h2></div>
        {!clientId && <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Google OAuth belum dikonfigurasi. Isi VITE_GOOGLE_CLIENT_ID pada environment frontend.</p>}
        {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        {busy && <p role="status" className="text-center text-sm text-slate-500">Memverifikasi akun…</p>}
        <label className="block text-sm font-medium text-slate-700">Email Google
          <input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="nama@student.unklab.ac.id" className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" />
        </label>
        <label className="block text-sm font-medium text-slate-700">Masuk sebagai
          <select required value={role} onChange={event => setRole(event.target.value as LoginRole | '')} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm">
            <option value="" disabled>Pilih peran...</option>
            <option value="student">User / Mahasiswa</option>
            <option value="admin">Admin / Staf</option>
          </select>
        </label>
        <button type="button" disabled={!canContinue || !googleReady || busy} onClick={startLogin} className="w-full rounded-lg bg-royal px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-950 disabled:cursor-not-allowed disabled:opacity-50">Masuk</button>
        <div className="space-y-2 border-t pt-4"><p className="text-center text-xs text-slate-500">Jika tombol Masuk tidak berhasil, gunakan:</p><div className="flex justify-center" ref={buttonRef} /></div>
        <p className="text-center text-xs text-slate-400">Email diverifikasi melalui Google. Akses Admin/Staf memerlukan email yang terdaftar.</p>
      </div>
    </section>
  </main>;
}
