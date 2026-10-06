"use client";

import clsx from "clsx";
import { ChevronDown, Crown, Medal, Target } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { TeamLogo } from "@/components/TeamLogo";
import { Card, EmptyState, Loading, PageHeader } from "@/components/ui";
import { superBowlName } from "@/lib/format";
import { useHallOfFame } from "@/lib/queries";

export default function HallOfFamePage() {
  const hof = useHallOfFame();
  const [open, setOpen] = useState<number | null>(null);
  if (hof.isLoading) return <Loading />;
  const data = hof.data!;

  return (
    <div className="space-y-6">
      <PageHeader title="Hall of Fame" subtitle="Die Legenden des Tippspiels – jede abgeschlossene Saison wird hier verewigt." />

      {data.seasons.length === 0 ? (
        <Card>
          <EmptyState icon={<Crown className="size-8" />} title="Noch keine abgeschlossene Saison">
            Nach dem Super Bowl wird der Sieger des Tippspiels automatisch aufgenommen.
          </EmptyState>
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {data.seasons.map((s) => (
            <section key={s.season_id} className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-gold/50 via-gold/10 to-nfc/30 p-px">
              <div className="relative h-full rounded-[23px] bg-ink-900/95 p-5 sm:p-6">
                <div className="pointer-events-none absolute -top-16 -right-10 size-56 rounded-full bg-gold/10 blur-3xl" />
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[11px] font-bold tracking-[0.3em] text-gold">SAISON {s.season_name}</p>
                    <p className="text-xs text-slate-400">{superBowlName(s.year)}</p>
                  </div>
                  {s.champion_team && (
                    <div className="flex items-center gap-2 text-right">
                      <div>
                        <p className="text-[10px] font-bold tracking-widest text-slate-500">NFL CHAMPION</p>
                        <p className="font-semibold text-white">{s.champion_team.short_name}</p>
                      </div>
                      <TeamLogo team={s.champion_team} size={44} glow />
                    </div>
                  )}
                </div>
                <div className="mt-5 flex items-center gap-4">
                  <div className="relative">
                    <Crown className="absolute -top-6 left-1/2 size-6 -translate-x-1/2 text-gold drop-shadow-[0_0_8px_rgb(245_196_81/0.8)]" />
                    <div className="flex size-20 items-center justify-center rounded-full bg-gradient-to-br from-gold to-amber-700 text-3xl shadow-[0_0_30px_-4px_rgb(245_196_81/0.7)]">
                      🏆
                    </div>
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-bold tracking-widest text-slate-400">TIPPSPIEL-SIEGER</p>
                    <p className="display truncate text-3xl font-bold text-white sm:text-4xl">{s.winner_display_name}</p>
                    <p className="text-gradient-gold display text-xl font-bold">{s.winner_points} Punkte</p>
                  </div>
                </div>
                <dl className="mt-5 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-xl bg-white/[0.04] p-2">
                    <dt className="text-[10px] text-slate-500 uppercase">Richtige Tipps</dt>
                    <dd className="display text-xl font-bold text-white">{s.winner_correct_winners}</dd>
                  </div>
                  <div className="rounded-xl bg-white/[0.04] p-2">
                    <dt className="text-[10px] text-slate-500 uppercase">Exakte Scores</dt>
                    <dd className="display text-xl font-bold text-white">{s.winner_exact_scores}</dd>
                  </div>
                  <div className="rounded-xl bg-white/[0.04] p-2">
                    <dt className="text-[10px] text-slate-500 uppercase">Super-Bowl-Tipp</dt>
                    <dd className="flex items-center justify-center gap-1.5 pt-0.5">
                      {s.winner_sb_pick_team ? (
                        <>
                          <TeamLogo team={s.winner_sb_pick_team} size={22} />
                          <span className="text-sm font-semibold text-white">{s.winner_sb_pick_team.abbreviation}</span>
                        </>
                      ) : (
                        <span className="text-slate-500">–</span>
                      )}
                    </dd>
                  </div>
                </dl>
                <button
                  onClick={() => setOpen(open === s.season_id ? null : s.season_id)}
                  className="mt-4 flex w-full items-center justify-center gap-1 text-xs font-semibold text-slate-400 hover:text-white"
                  aria-expanded={open === s.season_id}
                >
                  Abschlusstabelle <ChevronDown className={clsx("size-4 transition", open === s.season_id && "rotate-180")} />
                </button>
                {open === s.season_id && (
                  <ol className="mt-3 space-y-1">
                    {s.standings.map((r) => (
                      <li key={r.user_id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-white/5">
                        <span className={clsx("display w-6 font-bold", r.rank === 1 ? "text-gold" : "text-slate-400")}>{r.rank}</span>
                        <span className="flex-1 font-semibold text-slate-100">{r.display_name}</span>
                        {r.sb_pick_team && <TeamLogo team={r.sb_pick_team} size={18} />}
                        {r.champion_correct && <span title="Champion richtig">🏆</span>}
                        <span className="w-10 text-right font-bold text-white tabular-nums">{r.points}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      <Card title={<span className="flex items-center gap-2"><Medal className="size-4 text-gold" /> Ewige Tabelle</span>} accent="gold" bodyClassName="p-0">
        {data.all_time.length === 0 ? (
          <EmptyState title="Noch leer" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-sm">
              <thead className="text-[11px] tracking-wider text-slate-500 uppercase">
                <tr className="border-b border-white/5">
                  <th className="px-4 py-3 text-left">#</th>
                  <th className="px-4 py-3 text-left">Spieler</th>
                  <th className="px-3 py-3 text-right">Titel</th>
                  <th className="px-3 py-3 text-right">Saisons</th>
                  <th className="px-3 py-3 text-right">Punkte</th>
                  <th className="px-3 py-3 text-right">Ø Punkte</th>
                  <th className="px-3 py-3 text-right">Richtig</th>
                  <th className="px-3 py-3 text-right">Exakt</th>
                  <th className="px-3 py-3 text-right">Champion</th>
                  <th className="px-4 py-3 text-right">Bester Rang</th>
                </tr>
              </thead>
              <tbody>
                {data.all_time.map((r) => (
                  <tr key={r.user.id} className="border-b border-white/5 last:border-0">
                    <td className={clsx("display px-4 py-3 text-lg font-bold", r.rank === 1 ? "text-gold" : "text-slate-300")}>{r.rank}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-2">
                        <Avatar user={r.user} size={28} /> <span className="font-semibold text-white">{r.user.display_name}</span>
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right">
                      {r.titles > 0 ? <span className="font-bold text-gold">{"🏆".repeat(Math.min(r.titles, 5))}</span> : <span className="text-slate-600">0</span>}
                    </td>
                    <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{r.seasons_played}</td>
                    <td className="px-3 py-3 text-right font-bold text-white tabular-nums">{r.total_points}</td>
                    <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{r.avg_points}</td>
                    <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{r.correct_winners}</td>
                    <td className="px-3 py-3 text-right text-slate-300 tabular-nums">
                      <span className="inline-flex items-center gap-1">
                        <Target className="size-3 text-slate-500" />
                        {r.exact_scores}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{r.champion_hits}</td>
                    <td className="px-4 py-3 text-right text-slate-300 tabular-nums">{r.best_rank ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
