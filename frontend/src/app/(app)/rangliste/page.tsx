"use client";

import clsx from "clsx";
import { Crown, Trophy } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Trend } from "@/components/dashboard/Widgets";
import { Card, EmptyState, Loading, PageHeader, Select } from "@/components/ui";
import { useLeaderboard, useSelectedSeason } from "@/lib/queries";
import type { LeaderboardRow } from "@/lib/types";

function Podium({ rows }: { rows: LeaderboardRow[] }) {
  const top = [rows[1], rows[0], rows[2]].filter(Boolean);
  return (
    <div className="mx-auto grid max-w-3xl grid-cols-3 items-end gap-3 sm:gap-6">
      {top.map((r) => {
        const first = r.rank === 1 && r === rows[0];
        return (
          <div key={r.user.id} className="flex flex-col items-center text-center">
            <div className="relative">
              {first && <Crown className="absolute -top-7 left-1/2 size-7 -translate-x-1/2 text-gold drop-shadow-[0_0_10px_rgb(245_196_81/0.8)]" />}
              <Avatar user={r.user} size={first ? 84 : 64} ring={first} />
            </div>
            <p className="mt-2 truncate font-semibold text-white">{r.user.display_name}</p>
            <p className="display text-2xl font-bold text-gold">{r.points}</p>
            <div
              className={clsx(
                "mt-2 flex w-full items-start justify-center rounded-t-2xl pt-3",
                first ? "h-28 bg-gradient-to-b from-gold/40 to-gold/5" : r === rows[1] ? "h-20 bg-gradient-to-b from-slate-300/25 to-transparent" : "h-14 bg-gradient-to-b from-amber-700/30 to-transparent",
              )}
            >
              <span className="display text-3xl font-bold text-white/80">{r.rank}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function LeaderboardPage() {
  const [selected, setSelected] = useState<number | null>(null);
  const { id, season, seasons } = useSelectedSeason(selected);
  const board = useLeaderboard(id);
  const rows = board.data ?? [];

  return (
    <div className="space-y-5">
      <PageHeader title="Rangliste" subtitle={season ? `Saison ${season.name}${season.status === "COMPLETED" ? " · abgeschlossen" : ""}` : undefined}>
        {seasons.length > 1 && (
          <Select value={id ?? ""} onChange={(e) => setSelected(Number(e.target.value))} aria-label="Saison wählen" className="w-40">
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        )}
      </PageHeader>
      {board.isLoading && <Loading />}
      {!board.isLoading && rows.length === 0 && (
        <Card>
          <EmptyState icon={<Trophy className="size-8" />} title="Noch keine Wertung">Sobald das erste Spiel gewertet ist, erscheint hier die Rangliste.</EmptyState>
        </Card>
      )}
      {rows.length >= 3 && (
        <Card accent="gold" bodyClassName="pt-10">
          <Podium rows={rows} />
        </Card>
      )}
      {rows.length > 0 && (
        <Card bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-[11px] tracking-wider text-slate-500 uppercase">
                <tr className="border-b border-white/5">
                  <th className="px-4 py-3 text-left">Rang</th>
                  <th className="px-4 py-3 text-left">Spieler</th>
                  <th className="px-3 py-3 text-right">Punkte</th>
                  <th className="px-3 py-3 text-right">Richtige Sieger</th>
                  <th className="px-3 py-3 text-right">Falsch</th>
                  <th className="px-3 py-3 text-right">Exakt</th>
                  <th className="px-3 py-3 text-right">Trefferquote</th>
                  <th className="px-4 py-3 text-center">Champion</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const decided = r.correct_winners + r.wrong_picks;
                  return (
                    <tr key={r.user.id} className={clsx("border-b border-white/5 last:border-0", r.is_me && "bg-gold/[0.08]")}>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2">
                          <span className={clsx("display w-6 text-lg font-bold", r.rank === 1 ? "text-gold" : "text-slate-300")}>{r.rank}</span>
                          <Trend row={r} />
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-3">
                          <Avatar user={r.user} size={32} ring={r.is_me} />
                          <span className={clsx("font-semibold", r.is_me ? "text-gold" : "text-white")}>{r.user.display_name}</span>
                          {r.is_me && <span className="rounded bg-gold/20 px-1.5 text-[10px] font-bold text-gold">DU</span>}
                        </span>
                      </td>
                      <td className="display px-3 py-3 text-right text-xl font-bold text-white tabular-nums">{r.points}</td>
                      <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{r.correct_winners}</td>
                      <td className="px-3 py-3 text-right text-slate-400 tabular-nums">{r.wrong_picks}</td>
                      <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{r.exact_scores}</td>
                      <td className="px-3 py-3 text-right text-slate-300 tabular-nums">{decided ? Math.round((100 * r.correct_winners) / decided) : 0} %</td>
                      <td className="px-4 py-3 text-center">{r.champion_correct ? <Trophy className="mx-auto size-4 text-gold" /> : <span className="text-slate-600">–</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
