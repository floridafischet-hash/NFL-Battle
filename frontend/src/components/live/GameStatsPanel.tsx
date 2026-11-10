"use client";

import clsx from "clsx";
import { BarChart3, ChevronDown, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { dateTime } from "@/lib/format";
import { useLiveGameStats } from "@/lib/queries";
import type { LiveScoreboardGame } from "@/lib/types";

export function GameStatsPanel({ game }: { game: LiveScoreboardGame }) {
  const [open, setOpen] = useState(false);
  const query = useLiveGameStats(game.id, open);
  const teamOrder = useMemo(() => [game.away.abbreviation, game.home.abbreviation], [game]);
  const [activeTeam, setActiveTeam] = useState(teamOrder[0]);

  useEffect(() => setActiveTeam(teamOrder[0]), [teamOrder]);

  const data = query.data;
  const teams = data ? [...data.teams].sort((a, b) => teamOrder.indexOf(a.team.abbreviation) - teamOrder.indexOf(b.team.abbreviation)) : [];
  const playerTeams = data ? [...data.players].sort((a, b) => teamOrder.indexOf(a.team.abbreviation) - teamOrder.indexOf(b.team.abbreviation)) : [];
  const statKeys = Array.from(new Set(teams.flatMap((team) => team.statistics.map((stat) => stat.key))));
  const activePlayers = playerTeams.find((team) => team.team.abbreviation === activeTeam) ?? playerTeams[0];

  return (
    <div className="mt-3 border-t border-white/7 pt-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="focus-ring flex min-h-10 w-full items-center justify-between rounded-lg px-1 text-left text-xs font-bold text-gold"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2"><BarChart3 className="size-4" /> Spielstatistiken</span>
        <ChevronDown className={clsx("size-4 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="mt-3 space-y-4">
          {query.isLoading && <div className="flex items-center justify-center gap-2 rounded-xl bg-black/20 py-8 text-xs text-slate-400"><RefreshCw className="size-4 animate-spin" /> Boxscore wird geladen …</div>}
          {query.error && <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-300">{query.error.message}</div>}
          {data && (
            <>
              <section>
                <h4 className="mb-2 text-[10px] font-bold tracking-[0.16em] text-slate-500 uppercase">Teamvergleich</h4>
                <div className="overflow-hidden rounded-xl border border-white/7 bg-black/20">
                  <div className="grid grid-cols-[1fr_64px_64px] border-b border-white/7 px-3 py-2 text-center text-xs font-bold text-white">
                    <span className="text-left text-slate-500">Statistik</span>
                    {teams.map((team) => <span key={team.team.id}>{team.team.abbreviation}</span>)}
                  </div>
                  {statKeys.map((key) => {
                    const label = teams.flatMap((team) => team.statistics).find((stat) => stat.key === key)?.label ?? key;
                    return <div key={key} className="grid grid-cols-[1fr_64px_64px] px-3 py-1.5 text-center text-xs odd:bg-white/[0.025]">
                      <span className="truncate text-left text-slate-400">{label}</span>
                      {teams.map((team) => <span key={team.team.id} className="font-semibold tabular-nums text-slate-100">{team.statistics.find((stat) => stat.key === key)?.value ?? "–"}</span>)}
                    </div>;
                  })}
                </div>
              </section>

              {playerTeams.length > 0 && <section>
                <div className="mb-3 flex items-center justify-between gap-2">
                  <h4 className="text-[10px] font-bold tracking-[0.16em] text-slate-500 uppercase">Spieler</h4>
                  <div className="flex rounded-lg bg-black/25 p-1">
                    {playerTeams.map((team) => <button key={team.team.id} onClick={() => setActiveTeam(team.team.abbreviation)} className={clsx("focus-ring rounded-md px-3 py-1 text-[11px] font-bold transition", activePlayers?.team.abbreviation === team.team.abbreviation ? "bg-gold text-ink-950" : "text-slate-400 hover:text-white")}>{team.team.abbreviation}</button>)}
                  </div>
                </div>
                <div className="space-y-3">
                  {activePlayers?.categories.map((category) => <div key={category.key} className="overflow-hidden rounded-xl border border-white/7 bg-black/20">
                    <h5 className="border-b border-white/7 px-3 py-2 text-xs font-bold text-white">{category.label}</h5>
                    <div className="scrollbar-thin overflow-x-auto">
                      <table className="w-full min-w-max text-xs">
                        <thead><tr className="text-[10px] text-slate-500"><th className="px-3 py-2 text-left font-semibold">Spieler</th>{category.labels.map((label) => <th key={label} className="px-2 py-2 text-right font-semibold">{label}</th>)}</tr></thead>
                        <tbody className="divide-y divide-white/5">{category.athletes.map((athlete) => <tr key={athlete.id}><td className="px-3 py-2 font-semibold whitespace-nowrap text-slate-200">{athlete.name}{athlete.position && <span className="ml-1 text-[10px] font-normal text-slate-600">{athlete.position}</span>}</td>{athlete.stats.map((value, index) => <td key={index} className="px-2 py-2 text-right tabular-nums text-slate-300">{value ?? "–"}</td>)}</tr>)}</tbody>
                      </table>
                    </div>
                  </div>)}
                </div>
              </section>}

              <p className="text-[10px] text-slate-600">Stand: {dateTime(data.updated_at)} · Quelle: {data.source}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
