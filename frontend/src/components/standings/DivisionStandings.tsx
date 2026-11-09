"use client";

import clsx from "clsx";
import { ChevronDown, Star } from "lucide-react";

import type { LiveDivisionStanding } from "@/lib/types";

export function DivisionStandings({ divisions, favorites }: { divisions: LiveDivisionStanding[]; favorites: Set<string> }) {
  const conferences = ["AFC", "NFC"] as const;
  const detailStat = (label: string, value: string | null, positive = false) => <div className="rounded-lg border border-white/5 bg-black/20 px-2 py-2 text-center">
    <span className="block text-[9px] font-bold tracking-wide text-slate-500 uppercase">{label}</span>
    <span className={clsx("mt-0.5 block text-xs font-semibold tabular-nums", positive && value?.startsWith("+") ? "text-emerald-300" : "text-slate-200")}>{value ?? "–"}</span>
  </div>;
  return <section aria-label="NFL Division Standings">
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
      {conferences.map((conference) => <div key={conference} className="min-w-0 space-y-4">
        <div className={clsx("rounded-2xl border px-4 py-3", conference === "AFC" ? "border-afc/30 bg-afc/10" : "border-nfc/30 bg-nfc/10")}>
          <p className={clsx("display text-xl font-bold", conference === "AFC" ? "text-afc-soft" : "text-nfc-soft")}>{conference} Conference</p>
        </div>
        {divisions.filter((division) => division.conference === conference).map((division) => <div key={division.abbreviation} className={clsx("overflow-hidden rounded-2xl border bg-ink-900/80 shadow-xl shadow-black/10", conference === "AFC" ? "border-afc/20" : "border-nfc/20")}>
          <div className="grid grid-cols-[1fr_34px_34px_46px_22px] items-center gap-1 border-b border-white/7 bg-white/[0.025] px-3 py-2">
            <h2 className="text-xs font-bold tracking-wide text-white uppercase">{division.name}</h2>
            <span className="text-center text-[9px] font-bold text-slate-500">W</span><span className="text-center text-[9px] font-bold text-slate-500">L</span><span className="text-center text-[9px] font-bold text-slate-500">PCT</span><span />
          </div>
          <div className="divide-y divide-white/5">{division.teams.map((team) => {
            const favorite = favorites.has(team.slug);
            return <details key={team.slug} className={clsx("group", favorite && "bg-gold/[0.1] shadow-[inset_3px_0_0_#d6b35a]")}>
              <summary className="focus-ring grid cursor-pointer list-none grid-cols-[1fr_34px_34px_46px_22px] items-center gap-1 px-3 py-2.5 transition hover:bg-white/[0.035] [&::-webkit-details-marker]:hidden">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="w-3 text-right text-[10px] text-slate-600 tabular-nums">{team.rank}</span>
                  {team.logo ? <img src={team.logo} alt="" className="size-7 shrink-0 object-contain" /> : <span className="size-7 shrink-0" />}
                  <span className="min-w-0 flex-1 truncate text-sm font-bold text-white">{team.short_name || team.name}</span>
                  {favorite && <Star className="size-3 shrink-0 fill-gold text-gold" aria-label="Favoritenteam" />}
                </span>
                <span className="text-center text-xs font-bold text-white tabular-nums">{team.wins ?? "–"}</span>
                <span className="text-center text-xs font-bold text-white tabular-nums">{team.losses ?? "–"}</span>
                <span className="text-center text-xs font-semibold text-slate-300 tabular-nums">{team.win_percent ?? "–"}</span>
                <ChevronDown className="size-4 text-slate-500 transition group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div className="grid grid-cols-2 gap-2 border-t border-white/5 bg-black/15 px-3 py-3 sm:grid-cols-4">
                {detailStat("Unentsch.", team.ties)}{detailStat("Division", team.division)}{detailStat("Conference", team.conference)}{detailStat("Serie", team.streak)}
                {detailStat("Heim", team.home)}{detailStat("Auswärts", team.road)}{detailStat("Punkte PF/PA", `${team.points_for ?? "–"}/${team.points_against ?? "–"}`)}{detailStat("Differenz", team.differential, true)}
              </div>
            </details>;
          })}</div>
        </div>)}
      </div>)}
    </div>
  </section>;
}
