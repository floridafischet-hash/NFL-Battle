"use client";

import clsx from "clsx";
import { Loader2, X } from "lucide-react";
import {
  forwardRef,
  useEffect,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";

export function Card({
  children,
  className,
  title,
  action,
  accent,
  bodyClassName,
  id,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  action?: ReactNode;
  accent?: "afc" | "nfc" | "gold";
  bodyClassName?: string;
  id?: string;
}) {
  return (
    <section id={id} className={clsx("glass relative overflow-hidden rounded-2xl", className)}>
      {accent && (
        <div
          className={clsx(
            "absolute inset-x-0 top-0 h-px",
            accent === "afc" && "bg-gradient-to-r from-transparent via-afc to-transparent",
            accent === "nfc" && "bg-gradient-to-r from-transparent via-nfc to-transparent",
            accent === "gold" && "bg-gradient-to-r from-transparent via-gold to-transparent",
          )}
        />
      )}
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-white/5 px-4 py-3 sm:px-5">
          <h2 className="card-title text-sm text-slate-200 sm:text-[15px]">{title}</h2>
          {action}
        </header>
      )}
      <div className={clsx("p-4 sm:p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg"; loading?: boolean }
>(function Button({ variant = "secondary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition select-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" && "min-h-9 px-3 text-xs",
        size === "md" && "min-h-11 px-4 text-sm",
        size === "lg" && "min-h-12 px-6 text-base",
        variant === "primary" &&
          "bg-gradient-to-b from-gold-soft to-gold text-ink-950 shadow-[0_8px_24px_-8px_rgb(245_196_81/0.6)] hover:brightness-110",
        variant === "secondary" && "border border-white/10 bg-white/5 text-slate-100 hover:border-white/20 hover:bg-white/10",
        variant === "ghost" && "text-slate-300 hover:bg-white/5 hover:text-white",
        variant === "danger" && "border border-red-500/30 bg-red-500/15 text-red-200 hover:bg-red-500/25",
        variant === "success" && "border border-emerald-500/30 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25",
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
});

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "afc" | "nfc" | "gold" | "green" | "red" | "amber" | "live";
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-bold tracking-wider uppercase",
        tone === "neutral" && "bg-white/8 text-slate-300 ring-1 ring-white/10",
        tone === "afc" && "bg-afc/15 text-afc-soft ring-1 ring-afc/30",
        tone === "nfc" && "bg-nfc/15 text-nfc-soft ring-1 ring-nfc/30",
        tone === "gold" && "bg-gold/15 text-gold ring-1 ring-gold/30",
        tone === "green" && "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
        tone === "red" && "bg-red-500/15 text-red-300 ring-1 ring-red-500/30",
        tone === "amber" && "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
        tone === "live" && "bg-red-600 text-white",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("size-5 animate-spin text-slate-400", className)} />;
}

export function Loading({ label = "Lädt …" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-sm text-slate-400">
      <Spinner /> {label}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      {icon && <div className="mb-1 text-slate-500">{icon}</div>}
      <p className="font-semibold text-slate-200">{title}</p>
      {children && <div className="max-w-md text-sm text-slate-400">{children}</div>}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Unbekannter Fehler";
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{message}</div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label?: string }>(
  function Input({ label, className, id, ...rest }, ref) {
    const input = (
      <input
        ref={ref}
        id={id}
        className={clsx(
          "focus-ring min-h-11 w-full rounded-xl border border-white/10 bg-ink-900/80 px-3 text-sm text-white placeholder:text-slate-500",
          "focus:border-gold/60",
          className,
        )}
        {...rest}
      />
    );
    if (!label) return input;
    return (
      <label className="block space-y-1.5" htmlFor={id}>
        <span className="text-xs font-medium text-slate-400">{label}</span>
        {input}
      </label>
    );
  },
);

export function Select({
  label,
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  const select = (
    <select
      className={clsx(
        "focus-ring min-h-11 w-full rounded-xl border border-white/10 bg-ink-900/80 px-3 text-sm text-white",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
  if (!label) return select;
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-slate-400">{label}</span>
      {select}
    </label>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="absolute inset-0" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        className={clsx(
          "glass relative max-h-[92dvh] w-full animate-fade-up overflow-y-auto rounded-t-2xl sm:rounded-2xl",
          wide ? "sm:max-w-3xl" : "sm:max-w-lg",
        )}
      >
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/5 bg-ink-900/90 px-5 py-4">
          <h3 className="card-title text-base text-white">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white" aria-label="Schließen">
            <X className="size-5" />
          </button>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: { value: T; label: ReactNode; badge?: number }[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div className={clsx("scrollbar-thin flex gap-1 overflow-x-auto rounded-xl bg-white/5 p-1", className)} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={t.value === value}
          onClick={() => onChange(t.value)}
          className={clsx(
            "focus-ring flex min-h-10 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-semibold whitespace-nowrap transition",
            t.value === value ? "bg-white/12 text-white shadow" : "text-slate-400 hover:text-white",
          )}
        >
          {t.label}
          {t.badge ? (
            <span className="rounded-full bg-afc px-1.5 text-[10px] leading-4 font-bold text-white">{t.badge}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="display text-3xl font-bold text-white sm:text-4xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "gold" | "afc" | "nfc" | "green";
}) {
  return (
    <div className="rounded-xl border border-white/6 bg-white/[0.03] px-3 py-3">
      <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">{label}</p>
      <p
        className={clsx(
          "display mt-1 text-2xl font-bold",
          tone === "gold" && "text-gold",
          tone === "afc" && "text-afc-soft",
          tone === "nfc" && "text-nfc-soft",
          tone === "green" && "text-emerald-300",
          !tone && "text-white",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
