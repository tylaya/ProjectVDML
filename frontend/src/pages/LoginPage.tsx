import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Building2, CheckCircle2, ShieldCheck } from 'lucide-react';
import type { LoginRole } from '../types';

type AuthMode = 'login' | 'register' | 'forgot' | 'reset';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: { theme: string; size: string; shape: string; width: number },
          ) => void;
        };
      };
    };
  }
}

export function LoginPage({
  onPasswordLogin,
  onGoogleLogin,
  onRegister,
  onRequestPasswordReset,
  onResetPassword,
}: {
  onPasswordLogin: (email: string, password: string, role?: LoginRole) => Promise<void>;
  onGoogleLogin: (credential: string, email: string, role: LoginRole) => Promise<void>;
  onRegister: (credential: string, email: string, password: string) => Promise<void>;
  onRequestPasswordReset: (email: string) => Promise<void>;
  onResetPassword: (token: string, password: string) => Promise<void>;
}) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const modeRef = useRef<AuthMode>('login');
  const onGoogleLoginRef = useRef(onGoogleLogin);
  const onRegisterRef = useRef(onRegister);
  const emailRef = useRef('');
  const passwordRef = useRef('');
  const confirmPasswordRef = useRef('');
  const roleRef = useRef<LoginRole | ''>('');
  const googleInitialized = useRef(false);
  const [error, setError] = useState('');
  const [googleLoadError, setGoogleLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetToken] = useState(() => new URLSearchParams(window.location.search).get('reset_token') ?? '');
  const [mode, setMode] = useState<AuthMode>(() => new URLSearchParams(window.location.search).has('reset_token') ? 'reset' : 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState<LoginRole | ''>('');
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const normalizedEmail = email.trim().toLowerCase();
  const emailReady = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail);
  const studentEmailReady = /^s?\d{8}@student\.unklab\.ac\.id$/.test(normalizedEmail);
  const canUseGoogle =
    mode === 'register' ? studentEmailReady : mode === 'login' && emailReady && Boolean(role);

  useEffect(() => { onGoogleLoginRef.current = onGoogleLogin; }, [onGoogleLogin]);
  useEffect(() => { onRegisterRef.current = onRegister; }, [onRegister]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { emailRef.current = normalizedEmail; }, [normalizedEmail]);
  useEffect(() => { passwordRef.current = password; }, [password]);
  useEffect(() => { confirmPasswordRef.current = confirmPassword; }, [confirmPassword]);
  useEffect(() => { roleRef.current = role; }, [role]);
  useEffect(() => {
    if (!clientId) return;
    const initializeGoogle = () => {
      if (googleInitialized.current) return true;
      if (!window.google) return false;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: response => {
          const currentEmail = emailRef.current;
          const currentMode = modeRef.current;
          const currentPassword = passwordRef.current;
          setBusy(true);
          setError('');
          let operation: Promise<void>;
          if (currentMode === 'register') {
            if (!/^s?\d{8}@student\.unklab\.ac\.id$/.test(currentEmail)) {
              setError('Email mahasiswa harus berformat 12410292 atau s12410292@student.unklab.ac.id.');
              setBusy(false);
              return;
            }
            if (currentPassword.length < 8) {
              setError('Password minimal 8 karakter.');
              setBusy(false);
              return;
            }
            if (currentPassword !== confirmPasswordRef.current) {
              setError('Konfirmasi password tidak sama.');
              setBusy(false);
              return;
            }
            operation = onRegisterRef.current(response.credential, currentEmail, currentPassword);
          } else {
            const currentRole = roleRef.current;
            if (!currentEmail || !currentRole) {
              setError('Masukkan email dan pilih peran untuk login Google.');
              setBusy(false);
              return;
            }
            operation = onGoogleLoginRef.current(response.credential, currentEmail, currentRole);
          }
          void operation.catch(reason => {
            setError(reason instanceof Error ? reason.message : 'Login Google gagal.');
          }).finally(() => setBusy(false));
        },
      });
      googleInitialized.current = true;
      setGoogleLoadError('');
      setGoogleReady(true);
      return true;
    };
    if (initializeGoogle()) return;
    const script = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );
    if (!script) {
      setGoogleLoadError('Layanan Google Sign-In tidak ditemukan di halaman ini.');
      return;
    }
    const loadTimeout = window.setTimeout(() => {
      if (!googleInitialized.current) {
        setGoogleLoadError(
          'Layanan Google Sign-In belum merespons. Muat ulang halaman atau periksa koneksi.',
        );
      }
    }, 10000);
    const handleLoad = () => {
      if (!initializeGoogle()) {
        setGoogleLoadError('Layanan Google Sign-In gagal dimulai. Muat ulang halaman dan coba lagi.');
      } else {
        window.clearTimeout(loadTimeout);
      }
    };
    const handleError = () => {
      window.clearTimeout(loadTimeout);
      setGoogleLoadError(
        'Layanan Google Sign-In gagal dimuat. Periksa koneksi internet atau pemblokir skrip.',
      );
    };
    script.addEventListener('load', handleLoad);
    script.addEventListener('error', handleError);
    if (window.google) handleLoad();
    return () => {
      window.clearTimeout(loadTimeout);
      script.removeEventListener('load', handleLoad);
      script.removeEventListener('error', handleError);
    };
  }, [clientId]);

  useEffect(() => {
    if (!buttonRef.current) return;
    buttonRef.current.replaceChildren();
    if (!googleReady || !canUseGoogle || !window.google) return;
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: 'outline',
      size: 'large',
      shape: 'rectangular',
      width: Math.min(320, Math.floor(buttonRef.current.getBoundingClientRect().width)),
    });
  }, [canUseGoogle, googleReady, mode]);

  const submitPasswordLogin = async () => {
    setError('');
    if (!emailReady || !password) {
      setError('Masukkan email dan password.');
      return;
    }
    if (role === 'kost_owner') {
      setError('Pemilik kost harus masuk menggunakan Google.');
      return;
    }
    setBusy(true);
    try {
      await onPasswordLogin(normalizedEmail, password, role || undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Login gagal.');
    } finally {
      setBusy(false);
    }
  };

  const switchMode = () => {
    setError('');
    setMode(current => current === 'register' ? 'login' : 'register');
  };

  const submitResetRequest = async () => {
    setError('');
    if (!/^(s?\d{8})@student\.unklab\.ac\.id$/i.test(resetEmail.trim())) {
      setError('Masukkan email mahasiswa yang terdaftar.');
      return;
    }
    setBusy(true);
    try {
      await onRequestPasswordReset(resetEmail.trim().toLowerCase());
      setError('');
      setGoogleLoadError('Jika akun terdaftar, tautan reset akan dikirim ke email kampus Anda.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Permintaan reset password gagal.');
    } finally {
      setBusy(false);
    }
  };

  const submitNewPassword = async () => {
    setError('');
    if (!resetToken) {
      setError('Tautan reset tidak valid atau telah kedaluwarsa.');
      return;
    }
    if (password.length < 8 || password !== confirmPassword) {
      setError(password.length < 8 ? 'Password minimal 8 karakter.' : 'Konfirmasi password tidak sama.');
      return;
    }
    setBusy(true);
    try {
      await onResetPassword(resetToken, password);
      window.history.replaceState({}, '', window.location.pathname);
      setMode('login');
      setPassword('');
      setConfirmPassword('');
      setError('');
      setGoogleLoadError('Password berhasil diperbarui. Silakan masuk dengan password baru.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Reset password gagal.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="relative grid min-h-screen items-center justify-center gap-8 overflow-hidden bg-slate-50 p-4 sm:p-8 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14 lg:px-[7vw]">
      <div className="pointer-events-none absolute -left-36 -top-32 h-96 w-96 rounded-full bg-blue-100/70 blur-3xl" />
      <aside className="relative hidden min-h-[600px] flex-col justify-between overflow-hidden rounded-[2rem] bg-royal p-10 text-white shadow-2xl shadow-slate-900/15 lg:flex xl:p-14">
        <div className="pointer-events-none absolute -right-20 top-1/4 h-80 w-80 rounded-full border-[42px] border-white/[0.05]" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <span className="rounded-2xl bg-white/10 p-3 text-gold ring-1 ring-white/15"><Building2 size={25} /></span>
            <div><p className="text-sm font-bold tracking-[0.18em]">SIGAP-VD</p><p className="mt-0.5 text-xs text-slate-300">Village Dean · Universitas Klabat</p></div>
          </div>
          <div className="mt-24 max-w-xl">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-200">Sistem verifikasi hunian</p>
            <h1 className="mt-4 text-4xl font-bold leading-[1.12] tracking-tight xl:text-5xl">Administrasi hunian mahasiswa, lebih terarah.</h1>
            <p className="mt-5 max-w-lg text-sm leading-7 text-slate-300">Kelola pengajuan, bukti domisili, konfirmasi pemilik kost, dan pemeriksaan dalam satu portal terintegrasi.</p>
          </div>
          <div className="mt-10 space-y-4">
            {['Validasi hunian dengan data yang terstruktur', 'Konfirmasi penghuni langsung oleh pemilik kost', 'Berkas tersimpan dengan perlindungan enkripsi'].map(item => <p key={item} className="flex items-center gap-3 text-sm text-slate-200"><CheckCircle2 size={17} className="shrink-0 text-emerald-300" />{item}</p>)}
          </div>
        </div>
        <div className="relative flex items-center justify-between border-t border-white/10 pt-5 text-xs text-slate-400">
          <span className="inline-flex items-center gap-2"><ShieldCheck size={15} /> Akses terverifikasi</span>
          <span>Portal resmi Village Dean</span>
        </div>
      </aside>
      <section className="relative mx-auto w-full max-w-md overflow-hidden rounded-[1.75rem] border border-slate-200/80 bg-white shadow-xl shadow-slate-900/[0.07] lg:max-w-xl">
        <div className="border-b border-slate-100 px-7 pb-5 pt-7 sm:px-9">
          <div className="mb-5 inline-flex rounded-2xl bg-royal p-3 text-gold shadow-md shadow-royal/15 lg:hidden"><Building2 size={23} /></div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Portal Mahasiswa & Petugas</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">Selamat datang</h2>
          <p className="mt-1 text-sm text-slate-500">Masuk dengan akun terdaftar untuk melanjutkan.</p>
        </div>
        <form
          className="space-y-5 px-7 py-6 sm:px-9 sm:py-8"
          onSubmit={event => {
            event.preventDefault();
            if (mode === 'register') setError('Gunakan tombol Google untuk memverifikasi email kampus dan membuat akun.');
            else if (mode === 'forgot') void submitResetRequest();
            else if (mode === 'reset') void submitNewPassword();
            else void submitPasswordLogin();
          }}
        >
          <h3 className="font-semibold text-slate-900">
            {mode === 'register' ? 'Buat akun mahasiswa' : mode === 'forgot' ? 'Lupa password' : mode === 'reset' ? 'Atur password baru' : 'Masuk ke akun'}
          </h3>
          {!clientId && (
            <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Google OAuth belum dikonfigurasi. Isi VITE_GOOGLE_CLIENT_ID pada environment frontend.
            </p>
          )}
          {googleLoadError && (
            <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {googleLoadError}
            </p>
          )}
          {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
          {busy && <p role="status" className="text-center text-sm text-slate-500">Memverifikasi akun…</p>}
          {(mode === 'login' || mode === 'register') && <label className="block text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={event => setEmail(event.target.value)}
              placeholder={mode === 'register' ? '12410292@student.unklab.ac.id' : 'email@unklab.ac.id'}
              className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm"
            />
          </label>}
          {mode === 'forgot' && <label className="block text-sm font-medium text-slate-700">Email kampus mahasiswa<input type="email" autoComplete="email" required value={resetEmail} onChange={event => setResetEmail(event.target.value)} placeholder="12410292@student.unklab.ac.id" className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>}
          {(mode === 'login' || mode === 'register' || mode === 'reset') && <label className="block text-sm font-medium text-slate-700">
            Password
            <input
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={mode === 'login' ? undefined : 8}
              maxLength={128}
              required
              value={password}
              onChange={event => setPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm"
            />
          </label>}
          {(mode === 'register' || mode === 'reset') && (
            <>
              <label className="block text-sm font-medium text-slate-700">
                Konfirmasi password
                <input
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={128}
                  required
                  value={confirmPassword}
                  onChange={event => setConfirmPassword(event.target.value)}
                  className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm"
                />
              </label>
              <p className="text-xs text-slate-500">
                {mode === 'register' ? 'Email harus berformat 8 angka, dengan atau tanpa awalan s, di domain mahasiswa.' : 'Password baru minimal 8 karakter.'}
              </p>
            </>
          )}
          {mode === 'login' ? (
            <>
              <label className="block text-sm font-medium text-slate-700">
                Masuk sebagai
                <select
                  value={role}
                  onChange={event => setRole(event.target.value as LoginRole | '')}
                  className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm"
                >
                  <option value="">Deteksi otomatis untuk password</option>
                  <option value="student">Mahasiswa</option>
                  <option value="admin">Admin / Staf</option>
                  <option value="kost_owner">Pemilik Kost (Google)</option>
                </select>
                <span className="mt-1 block text-xs font-normal text-slate-500">
                  Admin/staf dapat memilih Mahasiswa untuk membuka portal mahasiswa.
                </span>
              </label>
              <button
                type="submit"
                disabled={busy}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-royal px-4 py-3 text-sm font-semibold text-white shadow-md shadow-royal/15 hover:bg-slate-800 disabled:opacity-50"
              >
                Masuk dengan password <ArrowUpRight size={16} />
              </button>
            </>
          ) : mode === 'register' ? (
            <p className="text-center text-sm text-slate-600">Buat akun dengan Google untuk memverifikasi bahwa email kampus tersebut milik Anda.</p>
          ) : mode === 'forgot' ? (
            <button type="button" onClick={() => void submitResetRequest()} disabled={busy} className="w-full rounded-xl bg-royal px-4 py-3 text-sm font-semibold text-white shadow-md shadow-royal/15 disabled:opacity-50">Kirim tautan reset</button>
          ) : (
            <button type="button" onClick={() => void submitNewPassword()} disabled={busy} className="w-full rounded-xl bg-royal px-4 py-3 text-sm font-semibold text-white shadow-md shadow-royal/15 disabled:opacity-50">Simpan password baru</button>
          )}
          {mode === 'login' && <button type="button" onClick={() => { setError(''); setGoogleLoadError(''); setMode('forgot'); }} className="w-full text-center text-sm font-medium text-royal underline">Lupa password?</button>}
          {(mode === 'register' || (role && mode === 'login')) && (
            <div className="space-y-2">
              <p className="text-center text-xs text-slate-500">
                {mode === 'register' ? 'Verifikasi dan daftar dengan Google:' : 'Masuk menggunakan tombol Google resmi:'}
              </p>
              <div className="flex justify-center" ref={buttonRef} />
            </div>
          )}
          {(mode === 'login' || mode === 'register') && <p className="text-center text-sm text-slate-600">
            {mode === 'login' ? 'Belum memiliki akun?' : 'Sudah memiliki akun?'}{' '}
            <button type="button" onClick={switchMode} className="font-semibold text-royal underline">
              {mode === 'login' ? 'Buat akun' : 'Masuk'}
            </button>
          </p>}
          {(mode === 'forgot' || mode === 'reset') && <button type="button" onClick={() => { setMode('login'); setError(''); setGoogleLoadError(''); }} className="w-full text-center text-sm font-semibold text-royal underline">Kembali ke login</button>}
          <p className="text-center text-xs text-slate-400">
            Akun admin hanya untuk email yang diizinkan backend. Pendaftaran mandiri hanya untuk mahasiswa.
          </p>
        </form>
      </section>
    </main>
  );
}
