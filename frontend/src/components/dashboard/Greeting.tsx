"use client";

import { useQuery } from "@tanstack/react-query";
import { Crown, Download, Share } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";
import { get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useInstallPrompt } from "@/lib/pwa";

export interface GreetingData {
  king_name: string | null;
  king_title: string;
}

function salutation(hour: number) {
  if (hour < 5) return "Na, noch wach";
  if (hour < 11) return "Guten Morgen";
  if (hour < 18) return "Servus";
  return "Guten Abend";
}

/** Welcome line on top of the dashboard plus the reigning champion ("König"), set by an admin. */
export function Greeting() {
  const { user } = useAuth();
  const data = useQuery({ queryKey: ["greeting"], queryFn: () => get<GreetingData>("/api/greeting"), staleTime: 60_000 });
  const pwa = useInstallPrompt();
  const [iosOpen, setIosOpen] = useState(false);
  const first = user?.display_name.split(" ")[0] ?? "";

  return (
    <section className="glass flex flex-col gap-3 rounded-3xl px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6" data-testid="greeting">
      <div>
        <h2 className="display text-2xl font-bold text-white sm:text-3xl">
          {salutation(new Date().getHours())}, {first}! 🏈
        </h2>
        <p className="text-sm text-slate-400">Schön, dass du da bist. Mal sehen, wer diese Saison die Krone holt.</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {data.data?.king_name && (
          <div
            className="flex items-center gap-3 rounded-2xl border border-gold/40 bg-gold/10 px-4 py-2 shadow-[0_0_24px_rgba(234,179,8,0.15)]"
            data-testid="king"
          >
            <Crown className="size-6 text-gold" aria-hidden />
            <div className="leading-tight">
              <p className="text-[11px] font-bold tracking-[0.25em] text-gold uppercase">{data.data.king_title}</p>
              <p className="display text-xl font-bold text-white">{data.data.king_name}</p>
            </div>
          </div>
        )}
        {!pwa.installed && pwa.canInstall && (
          <Button size="sm" onClick={() => pwa.install()}>
            <Download className="size-4" /> App installieren
          </Button>
        )}
        {!pwa.installed && !pwa.canInstall && pwa.iosHint && (
          <Button size="sm" variant="ghost" onClick={() => setIosOpen((v) => !v)}>
            <Share className="size-4" /> Als App nutzen
          </Button>
        )}
      </div>
      {iosOpen && (
        <p className="text-xs text-slate-300 sm:basis-full">
          Auf dem iPhone: unten auf <strong>Teilen</strong> tippen → <strong>„Zum Home-Bildschirm“</strong>. Dann startet das
          Tippspiel wie eine App im Vollbild.
        </p>
      )}
    </section>
  );
}
