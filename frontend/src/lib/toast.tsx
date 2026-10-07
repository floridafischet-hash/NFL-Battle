"use client";

import clsx from "clsx";
import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

type Kind = "success" | "error" | "info";
interface Toast {
  id: number;
  kind: Kind;
  title: string;
  body?: string;
}

interface ToastApi {
  success: (title: string, body?: string) => void;
  error: (title: string, body?: string) => void;
  info: (title: string, body?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (kind: Kind, title: string, body?: string) => {
      const id = nextId.current++;
      setToasts((t) => [...t.slice(-3), { id, kind, title, body }]);
      setTimeout(() => dismiss(id), kind === "error" ? 7000 : 4500);
    },
    [dismiss],
  );
  const value = useMemo<ToastApi>(
    () => ({
      success: (t, b) => push("success", t, b),
      error: (t, b) => push("error", t, b),
      info: (t, b) => push("info", t, b),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:items-end">
        {toasts.map((t) => {
          const Icon = t.kind === "success" ? CheckCircle2 : t.kind === "error" ? TriangleAlert : Info;
          return (
            <div
              key={t.id}
              role="status"
              className={clsx(
                "glass pointer-events-auto flex w-full max-w-sm animate-fade-up items-start gap-3 rounded-xl px-4 py-3",
                t.kind === "error" && "border-red-500/40",
                t.kind === "success" && "border-emerald-500/30",
              )}
            >
              <Icon
                className={clsx(
                  "mt-0.5 size-5 shrink-0",
                  t.kind === "success" && "text-emerald-400",
                  t.kind === "error" && "text-red-400",
                  t.kind === "info" && "text-gold",
                )}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white">{t.title}</p>
                {t.body && <p className="mt-0.5 whitespace-pre-line text-xs text-slate-300">{t.body}</p>}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                className="rounded p-1 text-slate-400 hover:text-white"
                aria-label="Meldung schließen"
              >
                <X className="size-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}
