import { useEffect, useRef, useState } from 'react';
import { Building2 } from 'lucide-react';
import type { LoginRole } from '../types';

type AuthMode = 'login' | 'register';

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
}: {
  onPasswordLogin: (email: string, password: string) => Promise<void>;
  onGoogleLogin: (credential: string, email: string, role: LoginRole) => Promise<void>;
  onRegister: (credential: string, email: string, password: string) => Promise<void>;
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
  const [mode, setMode] = useState<AuthMode>('login');
  const [error, setError] = useState('');
  const [googleLoadError, setGoogleLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState<LoginRole | ''>('');
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const normalizedEmail = email.trim().toLowerCase();
  const emailReady = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail);
  const studentEmailReady = /^s\d{8}@student\.unklab\.ac\.id$/.test(normalizedEmail);
  const canUseGoogle =
    mode === 'register' ? studentEmailReady : emailReady && Boolean(role);

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
            if (!/^s\d{8}@student\.unklab\.ac\.id$/.test(currentEmail)) {
              setError('Email mahasiswa harus berformat s22210609@student.unklab.ac.id.');
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
      width: 320,
    });
  }, [canUseGoogle, googleReady, mode]);

  const validateRegistration = async () => {
    setError('');
    if (!studentEmailReady) {
      setError('Email mahasiswa harus berformat s22210609@student.unklab.ac.id.');
      return;
    }
    if (password.length < 8) {
      setError('Password minimal 8 karakter.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Konfirmasi password tidak sama.');
      return;
    }
    setBusy(true);
    try {
      await onRegister('', normalizedEmail, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Pendaftaran akun gagal.');
    } finally {
      setBusy(false);
    }
  };

  const submitPasswordLogin = async () => {
    setError('');
    if (!emailReady || !password) {
      setError('Masukkan email dan password.');
      return;
    }
    setBusy(true);
    try {
      await onPasswordLogin(normalizedEmail, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Login gagal.');
    } finally {
      setBusy(false);
    }
  };

  const switchMode = () => {
    setError('');
    setMode(current => current === 'login' ? 'register' : 'login');
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <section className="w-full max-w-md overflow-hidden rounded-2xl border bg-white shadow-sm">
        <div className="bg-royal px-7 py-8 text-white">
          <div className="mb-5 inline-flex rounded-xl bg-gold p-3 text-royal">
            <Building2 size={24} />
          </div>
          <h1 className="text-xl font-bold">SIGAP-VD</h1>
          <p className="mt-1 text-sm text-purple-100">Portal Village Dean · Universitas Klabat</p>
        </div>
        <form
          className="space-y-5 p-7"
          onSubmit={event => {
            event.preventDefault();
            if (mode === 'register') void validateRegistration();
            else void submitPasswordLogin();
          }}
        >
          <h2 className="font-semibold text-slate-900">
            {mode === 'register' ? 'Buat akun mahasiswa' : 'Masuk ke akun'}
          </h2>
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
          <label className="block text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={event => setEmail(event.target.value)}
              placeholder={mode === 'register' ? 's22210609@student.unklab.ac.id' : 'email@unklab.ac.id'}
              className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Password
            <input
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              minLength={mode === 'register' ? 8 : undefined}
              maxLength={128}
              required
              value={password}
              onChange={event => setPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm"
            />
          </label>
          {mode === 'register' && (
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
                Email harus berformat s + 8 angka di domain mahasiswa.
              </p>
            </>
          )}
          {mode === 'login' ? (
            <>
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded-lg bg-royal px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-950 disabled:opacity-50"
              >
                Masuk
              </button>
              <div className="border-t pt-4">
                <label className="block text-sm font-medium text-slate-700">
                  Atau masuk dengan Google sebagai
                  <select
                    value={role}
                    onChange={event => setRole(event.target.value as LoginRole | '')}
                    className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm"
                  >
                    <option value="">Pilih peran...</option>
                    <option value="student">Mahasiswa</option>
                    <option value="admin">Admin / Staf</option>
                  </select>
                </label>
              </div>
            </>
          ) : (
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-royal px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-950 disabled:opacity-50"
            >
              Buat akun
            </button>
          )}
          {role && mode === 'login' && (
            <div className="space-y-2">
              <p className="text-center text-xs text-slate-500">
                Masuk menggunakan tombol Google resmi:
              </p>
              <div className="flex justify-center" ref={buttonRef} />
            </div>
          )}
          <p className="text-center text-sm text-slate-600">
            {mode === 'login' ? 'Belum memiliki akun?' : 'Sudah memiliki akun?'}{' '}
            <button type="button" onClick={switchMode} className="font-semibold text-royal underline">
              {mode === 'login' ? 'Buat akun' : 'Masuk'}
            </button>
          </p>
          <p className="text-center text-xs text-slate-400">
            Akun admin hanya untuk email yang diizinkan backend. Pendaftaran mandiri hanya untuk mahasiswa.
          </p>
        </form>
      </section>
    </main>
  );
}
