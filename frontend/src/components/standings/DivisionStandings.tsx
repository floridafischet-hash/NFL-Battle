"use client";

import clsx from "clsx";
import { Star } from "lucide-react";

import type { LiveDivisionStanding } from "@/lib/types";

export function DivisionStandings({ divisions, favorites }: { divisions: LiveDivisionStanding[]; favorites: Set<string> }) {
  const conferences = ["AFC", "NFC"] as const;
  const stat = (label: string, value: string | null, positive = false) => <span className="text-center">
    <span className="block text-[9px] font-bold tracking-wide text-slate-600 uppercase">{label}</span>
    <span className={clsx("block text-xs font-semibold tabular-nums", positive && value?.startsWith("+") ? "text-emerald-300" : "text-slate-300")}>{value ?? "–"}</span>
  </span>;
  return <section className="rounded-3xl border border-white/10 bg-black/20 p-3 sm:p-5" aria-label="NFL Division Standings">
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {conferences.map((conference) => <div key={conference} className="min-w-0 space-y-4">
        <div className={clsx("rounded-xl border px-3 py-2 text-center", conference === "AFC" ? "border-afc/30 bg-afc/10" : "border-nfc/30 bg-nfc/10")}>
          <p className={clsx("display text-xl font-bold", conference === "AFC" ? "text-afc-soft" : "text-nfc-soft")}>{conference}</p>
        </div>
        {divisions.filter((division) => division.conference === conference).map((division) => <div key={division.abbreviation} className={clsx("overflow-hidden rounded-xl border bg-ink-900/80", conference === "AFC" ? "border-afc/20" : "border-nfc/20")}>
          <h2 className="border-b border-white/7 px-3 py-2 text-center text-xs font-bold tracking-wide text-white uppercase">{division.name}</h2>
          <div className="divide-y divide-white/5">{division.teams.map((team) => {
            const favorite = favorites.has(team.slug);
            return <div key={team.slug} className={clsx("p-3", favorite && "bg-gold/[0.12] shadow-[inset_3px_0_0_#d6b35a]")}>
              <div className="flex items-center gap-2">
                <span className="w-4 text-right text-[10px] text-slate-600 tabular-nums">{team.rank}</span>
                {team.logo ? <img src={team.logo} alt="" className="size-8 shrink-0 object-contain" /> : <span className="size-8 shrink-0" />}
                <span className="min-w-0 flex-1 truncate text-sm font-bold text-white">{team.name}</span>
                <span className="text-xs font-bold text-white tabular-nums">{team.wins}-{team.losses}{team.ties !== "0" ? `-${team.ties}` : ""}</span>
                {favorite && <Star className="size-3.5 shrink-0 fill-gold text-gold" aria-label="Favoritenteam" />}
              </div>
              <div className="mt-2 grid grid-cols-4 gap-x-2 gap-y-1 border-t border-white/5 pt-2">
                {stat("PCT", team.win_percent)}{stat("DIV", team.division)}{stat("CONF", team.conference)}{stat("Serie", team.streak)}
                {stat("Heim", team.home)}{stat("Ausw", team.road)}{stat("PF/PA", `${team.points_for ?? "–"}/${team.points_against ?? "–"}`)}{stat("Diff", team.differential, true)}
              </div>
            </div>;
          })}</div>
        </div>)}
      </div>)}
    </div>
  </section>;
}
