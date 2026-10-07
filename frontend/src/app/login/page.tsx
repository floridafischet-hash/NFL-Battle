"use client";

import { Lock, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { BrandMark } from "@/components/Brand";
import { Button } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, status } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden px-4 py-10">
      <div className="stadium-bg" aria-hidden />
      <div className="pointer-events-none absolute top-[12%] -left-40 size-[520px] rounded-full bg-afc/20 blur-[120px]" />
      <div className="pointer-events-none absolute -right-40 bottom-[10%] size-[520px] rounded-full bg-nfc/20 blur-[120px]" />

      <div className="relative w-full max-w-md animate-fade-up">
        <div className="mb-8 text-center">
          <BrandMark size={84} className="mx-auto drop-shadow-[0_0_30px_rgba(245,196,81,0.35)]" />
          <p className="display mt-5 text-sm font-semibold tracking-[0.5em] text-slate-400">NFL PLAYOFFS</p>
          <h1 className="display mt-1 text-5xl font-bold text-white sm:text-6xl">
            Bracket <span className="text-gradient-gold">Battle</span>
          </h1>
          <div className="mx-auto mt-4 flex max-w-xs items-center gap-3 text-xs font-bold tracking-[0.3em] uppercase">
            <span className="h-px flex-1 bg-gradient-to-r from-transparent to-afc" />
            <span className="text-afc-soft">AFC</span>
            <span className="text-slate-500">vs</span>
            <span className="text-nfc-soft">NFC</span>
            <span className="h-px flex-1 bg-gradient-to-l from-transparent to-nfc" />
          </div>
        </div>

        <form onSubmit={submit} className="glass space-y-4 rounded-3xl p-6 sm:p-8">
          <h2 className="card-title text-center text-lg text-white">Anmelden</h2>
          <label className="block">
            <span className="sr-only">Benutzername</span>
            <div className="flex min-h-12 items-center gap-3 rounded-xl border border-white/10 bg-ink-900/80 px-3 focus-within:border-gold/60">
              <User className="size-5 text-slate-500" />
              <input
                name="username"
                autoComplete="username"
                placeholder="Benutzername"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-12 w-full bg-transparent text-white outline-none placeholder:text-slate-500"
                required
                autoFocus
              />
            </div>
          </label>
          <label className="block">
            <span className="sr-only">Passwort</span>
            <div className="flex min-h-12 items-center gap-3 rounded-xl border border-white/10 bg-ink-900/80 px-3 focus-within:border-gold/60">
              <Lock className="size-5 text-slate-500" />
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Passwort"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 w-full bg-transparent text-white outline-none placeholder:text-slate-500"
                required
              />
            </div>
          </label>
          {error && (
            <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy}>
            Los geht&apos;s
          </Button>
          <p className="text-center text-xs text-slate-500">Zugang erhältst du von deinem Tippspiel-Admin.</p>
        </form>
      </div>
    </div>
  );
}
