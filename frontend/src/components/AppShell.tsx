"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  BarChart3,
  Bell,
  CalendarDays,
  ChevronDown,
  Crown,
  GitCompareArrows,
  LayoutDashboard,
  ListOrdered,
  LogOut,
  Menu,
  MessageSquare,
  Network,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { post } from "@/lib/api";
import { useAuth, useMe } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { useCurrentSeason, useNotifications } from "@/lib/queries";
import { useRealtime } from "@/lib/realtime";

import { Avatar } from "./Avatar";
import { Brand } from "./Brand";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/bracket", label: "Mein Bracket", icon: Network },
  { href: "/spiele", label: "Spiele", icon: CalendarDays },
  { href: "/rangliste", label: "Rangliste", icon: ListOrdered },
  { href: "/brackets", label: "Alle Brackets", icon: GitCompareArrows },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/statistiken", label: "Statistiken", icon: BarChart3 },
  { href: "/hall-of-fame", label: "Hall of Fame", icon: Crown },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const me = useMe();
  const items = me.is_admin ? [...NAV, { href: "/admin", label: "Admin", icon: ShieldCheck }] : NAV;
  return (
    <nav className="flex flex-col gap-1" aria-label="Hauptnavigation">
      {items.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={clsx(
              "focus-ring group relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold transition",
              active ? "bg-white/[0.08] text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-white",
            )}
          >
            {active && (
              <span className="absolute top-2 bottom-2 left-0 w-1 rounded-full bg-gradient-to-b from-afc via-gold to-nfc" />
            )}
            <Icon className={clsx("size-5", active ? "text-gold" : "text-slate-500 group-hover:text-slate-300")} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function Sidebar() {
  const season = useCurrentSeason();
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col border-r border-white/5 bg-ink-950/70 px-4 py-5 backdrop-blur-xl lg:flex">
      <Link href="/" className="focus-ring mb-8 rounded-xl px-2">
        <Brand />
      </Link>
      <NavLinks />
      <div className="mt-auto rounded-xl border border-white/5 bg-white/[0.03] p-3">
        <p className="text-[11px] font-medium tracking-wider text-slate-500 uppercase">Saison</p>
        <p className="display text-lg font-semibold text-white">{season.data?.name ?? "—"}</p>
        <p className="text-xs text-slate-400">
          {season.data?.status === "COMPLETED" ? "Abgeschlossen" : season.data ? "Playoffs laufen" : "Keine aktive Saison"}
        </p>
      </div>
    </aside>
  );
}

function useClickOutside(ref: React.RefObject<HTMLElement | null>, onOutside: () => void, active: boolean) {
  useEffect(() => {
    if (!active) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOutside();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [ref, onOutside, active]);
}

function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);
  const { data } = useNotifications();
  const qc = useQueryClient();
  const router = useRouter();
  const readAll = useMutation({
    mutationFn: () => post("/api/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const openItem = async (id: number, link: string | null) => {
    setOpen(false);
    await post(`/api/notifications/${id}/read`).catch(() => undefined);
    qc.invalidateQueries({ queryKey: ["notifications"] });
    if (link) router.push(link);
  };
  const unread = data?.unread ?? 0;
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="focus-ring relative flex size-11 items-center justify-center rounded-xl text-slate-300 hover:bg-white/5 hover:text-white"
        aria-label={`Benachrichtigungen (${unread} ungelesen)`}
        aria-expanded={open}
      >
        <Bell className="size-5" />
        {unread > 0 && (
          <span className="absolute top-1.5 right-1.5 flex min-w-5 items-center justify-center rounded-full bg-afc px-1 text-[10px] leading-5 font-bold text-white shadow-[0_0_12px_rgb(239_51_73/0.8)]">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="glass absolute right-0 z-50 mt-2 w-[min(92vw,380px)] animate-fade-up overflow-hidden rounded-2xl">
          <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
            <p className="card-title text-sm">Benachrichtigungen</p>
            {unread > 0 && (
              <button onClick={() => readAll.mutate()} className="text-xs font-semibold text-gold hover:underline">
                Alle gelesen
              </button>
            )}
          </div>
          <ul className="scrollbar-thin max-h-[60vh] overflow-y-auto">
            {(data?.items ?? []).length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-400">Keine Benachrichtigungen</li>}
            {data?.items.map((n) => (
              <li key={n.id}>
                <button
                  onClick={() => openItem(n.id, n.link)}
                  className="flex w-full gap-3 px-4 py-3 text-left hover:bg-white/5"
                >
                  <span className={clsx("mt-1.5 size-2 shrink-0 rounded-full", n.read ? "bg-transparent" : "bg-gold")} />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-slate-100">{n.title}</span>
                    {n.body && <span className="line-clamp-2 block text-xs text-slate-400">{n.body}</span>}
                    <span className="mt-0.5 block text-[11px] text-slate-500">{relativeTime(n.created_at)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const me = useMe();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="focus-ring flex min-h-11 items-center gap-2 rounded-xl px-1.5 hover:bg-white/5 sm:px-2"
        aria-expanded={open}
        aria-label="Benutzermenü"
      >
        <Avatar user={me} size={34} />
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-semibold text-white">{me.display_name}</span>
          <span className="block text-[11px] text-slate-400">{me.is_admin ? "Admin" : "Spieler"}</span>
        </span>
        <ChevronDown className="hidden size-4 text-slate-400 sm:block" />
      </button>
      {open && (
        <div className="glass absolute right-0 z-50 mt-2 w-56 animate-fade-up overflow-hidden rounded-2xl py-1">
          <Link href="/profil" onClick={() => setOpen(false)} className="flex min-h-11 items-center gap-3 px-4 text-sm text-slate-200 hover:bg-white/5">
            <UserRound className="size-4" /> Profil
          </Link>
          <button onClick={logout} className="flex min-h-11 w-full items-center gap-3 px-4 text-sm text-red-300 hover:bg-white/5">
            <LogOut className="size-4" /> Abmelden
          </button>
        </div>
      )}
    </div>
  );
}

function Header({ onMenu }: { onMenu: () => void }) {
  const { connected } = useRealtime();
  const { logout } = useAuth();
  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-ink-950/60 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-2 px-3 sm:px-6">
        <button
          onClick={onMenu}
          className="focus-ring flex size-11 items-center justify-center rounded-xl text-slate-300 hover:bg-white/5 lg:hidden"
          aria-label="Menü öffnen"
        >
          <Menu className="size-6" />
        </button>
        <Link href="/" className="lg:hidden">
          <Brand compact />
        </Link>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <span
            className={clsx(
              "hidden items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold tracking-wider uppercase md:flex",
              connected ? "bg-emerald-500/10 text-emerald-300" : "bg-white/5 text-slate-400",
            )}
            title={connected ? "Live-Verbindung aktiv" : "Verbinde …"}
          >
            <span className={clsx("size-2 rounded-full", connected ? "animate-pulse bg-emerald-400" : "bg-slate-500")} />
            {connected ? "Live" : "Offline"}
          </span>
          <NotificationsBell />
          <UserMenu />
          <button
            onClick={logout}
            className="focus-ring hidden size-11 items-center justify-center rounded-xl text-slate-400 hover:bg-white/5 hover:text-red-300 sm:flex"
            aria-label="Abmelden"
            title="Abmelden"
          >
            <LogOut className="size-5" />
          </button>
        </div>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  const pathname = usePathname();
  useEffect(() => setDrawer(false), [pathname]);
  return (
    <div className="min-h-dvh">
      <div className="stadium-bg" aria-hidden />
      <Sidebar />
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 flex w-[82vw] max-w-[300px] animate-fade-up flex-col bg-ink-950 px-4 py-5">
            <div className="mb-6 flex items-center justify-between">
              <Brand compact />
              <button
                onClick={() => setDrawer(false)}
                className="flex size-11 items-center justify-center rounded-xl text-slate-300 hover:bg-white/5"
                aria-label="Menü schließen"
              >
                <X className="size-6" />
              </button>
            </div>
            <NavLinks onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}
      <div className="lg:pl-[248px]">
        <Header onMenu={() => setDrawer(true)} />
        <main className="mx-auto w-full max-w-[1800px] px-3 py-5 sm:px-6 sm:py-7">{children}</main>
      </div>
    </div>
  );
}
