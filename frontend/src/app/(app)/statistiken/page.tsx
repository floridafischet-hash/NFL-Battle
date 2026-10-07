"use client";

import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Flame, Target, Trophy } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Card, EmptyState, Loading, PageHeader, Select, StatTile } from "@/components/ui";
import { get } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { percent } from "@/lib/format";
import { usePlayers, useSelectedSeason, useUserStats } from "@/lib/queries";
import type { SeasonStatsSummary, UserRef, UserStats } from "@/lib/types";

interface CompareStats {
  a: UserStats;
  b: UserStats;
  head_to_head: { a_better: number; b_better: number; equal: number };
  same_picks: number;
  compared_picks: number;
  agreement: number;
}

interface Overview {
  table: (SeasonStatsSummary & { user: UserRef; rank: number })[];
  matches_final: number;
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  return (
    <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
      <div className="h-full rounded-full transition-all" style={{ width: `${max ? (100 * value) / max : 0}%`, background: color }} />
    </div>
  );
}

export default function StatsPage() {
  const me = useMe();
  const [selected, setSelected] = useState<number | null>(null);
  const { id, season, seasons } = useSelectedSeason(selected);
  const stats = useUserStats("me", id);
  const players = usePlayers();
  const [friend, setFriend] = useState("");
  const compare = useQuery({
    queryKey: ["stats", "compare", id, friend],
    queryFn: () => get<CompareStats>(`/api/stats/compare?a=me&b=${friend}&season_id=${id}`),
    enabled: !!friend && id != null,
  });
  const overview = useQuery({
    queryKey: ["stats", "overview", id],
    queryFn: () => get<Overview>(`/api/stats/overview?season_id=${id}`),
    enabled: id != null,
  });

  if (stats.isLoading) return <Loading />;
  const s = stats.data;
  const cur = s?.season;
  const maxHistory = Math.max(1, ...(s?.history.map((h) => h.points) ?? [1]));

  return (
    <div className="space-y-5">
      <PageHeader title="Statistiken" subtitle={season ? `Saison ${season.name}` : undefined}>
        {seasons.length > 1 && (
          <Select value={id ?? ""} onChange={(e) => setSelected(Number(e.target.value))} aria-label="Saison wählen" className="w-40">
            {seasons.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </Select>
        )}
      </PageHeader>

      {cur && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          <StatTile label="Gesamtpunkte" value={cur.points} tone="gold" hint={cur.rank ? `Rang ${cur.rank} von ${cur.participants}` : undefined} />
          <StatTile label="Trefferquote" value={percent(cur.hit_rate)} tone="green" />
          <StatTile label="Richtige Sieger" value={cur.correct_winners} />
          <StatTile label="Falsche Tipps" value={cur.wrong_picks} tone="afc" hint={cur.missed_picks ? `+${cur.missed_picks} ohne Tipp` : undefined} />
          <StatTile label="Exakte Scores" value={cur.exact_scores} tone="gold" />
          <StatTile label="Beste Serie" value={cur.best_streak} hint={`aktuell ${cur.current_streak}`} />
          <StatTile label="SB-Sieger richtig" value={s.totals.champion_hits} hint="alle Saisons" />
          <StatTile label="Titel" value={s.totals.titles} tone="gold" hint={`${s.totals.seasons_played} Saisons`} />
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><Target className="size-4 text-gold" /> Trefferquote je Runde</span>}>
          {s?.rounds.every((r) => r.total === 0) ? (
            <EmptyState title="Noch keine gewerteten Spiele" />
          ) : (
            <ul className="space-y-3">
              {s?.rounds.map((r) => (
                <li key={r.round} className="flex items-center gap-3 text-sm">
                  <span className="w-44 shrink-0 text-slate-300">{r.label}</span>
                  <Bar value={r.correct} max={r.total} color="linear-gradient(90deg,#ef3349,#f5c451,#2f7bff)" />
                  <span className="w-14 shrink-0 text-right text-slate-400 tabular-nums">
                    {r.correct}/{r.total}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={<span className="flex items-center gap-2"><Trophy className="size-4 text-gold" /> Saisonvergleich</span>}>
          {!s?.history.length ? (
            <EmptyState title="Noch keine Saison gespielt" />
          ) : (
            <ul className="space-y-3">
              {s.history.map((h) => (
                <li key={h.season_id} className="flex items-center gap-3 text-sm">
                  <span className="w-24 shrink-0 font-semibold text-slate-200">{h.season_name}</span>
                  <Bar value={h.points} max={maxHistory} color={h.rank === 1 ? "#f5c451" : "#2f7bff"} />
                  <span className="w-28 shrink-0 text-right text-slate-400">
                    <strong className="text-white">{h.points} P.</strong> · #{h.rank}/{h.participants}
                    {h.champion_correct && " 🏆"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title={<span className="flex items-center gap-2"><Flame className="size-4 text-gold" /> Vergleich mit Freunden</span>} accent="gold">
        <div className="mb-4 max-w-xs">
          <Select value={friend} onChange={(e) => setFriend(e.target.value)} aria-label="Freund wählen">
            <option value="">– Freund wählen –</option>
            {(players.data ?? [])
              .filter((p) => p.id !== me.id)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
          </Select>
        </div>
        {compare.isLoading && friend && <Loading />}
        {compare.data && (
          <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
            {[compare.data.a, compare.data.b].map((u, i) => (
              <div key={u.user.id} className={clsx("rounded-2xl border border-white/8 bg-white/[0.03] p-4", i === 1 && "md:order-3")}>
                <div className="mb-3 flex items-center gap-3">
                  <Avatar user={u.user} size={40} />
                  <p className="display text-xl font-bold text-white">{u.user.display_name}</p>
                </div>
                <dl className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <dt className="text-[10px] text-slate-500 uppercase">Punkte</dt>
                    <dd className="display text-2xl font-bold text-gold">{u.season?.points ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] text-slate-500 uppercase">Quote</dt>
                    <dd className="display text-2xl font-bold text-white">{Math.round(u.season?.hit_rate ?? 0)}%</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] text-slate-500 uppercase">Exakt</dt>
                    <dd className="display text-2xl font-bold text-white">{u.season?.exact_scores ?? 0}</dd>
                  </div>
                </dl>
              </div>
            ))}
            <div className="text-center md:order-2">
              <p className="display text-4xl font-bold text-white">
                {compare.data.head_to_head.a_better} : {compare.data.head_to_head.b_better}
              </p>
              <p className="text-xs text-slate-400">Duelle (mehr Punkte im Spiel), {compare.data.head_to_head.equal} gleich</p>
              <p className="mt-2 text-sm text-slate-300">
                Übereinstimmung: <strong className="text-white">{percent(compare.data.agreement)}</strong>
              </p>
            </div>
          </div>
        )}
        {!friend && <p className="text-sm text-slate-400">Wähle einen Freund für den direkten Vergleich.</p>}
      </Card>

      <Card title="Alle Spieler" bodyClassName="p-0">
        {overview.isLoading ? (
          <Loading />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-[11px] tracking-wider text-slate-500 uppercase">
                <tr className="border-b border-white/5">
                  <th className="px-4 py-3 text-left">#</th>
                  <th className="px-4 py-3 text-left">Spieler</th>
                  <th className="px-3 py-3 text-right">Punkte</th>
                  <th className="px-3 py-3 text-right">Quote</th>
                  <th className="px-3 py-3 text-right">Richtig</th>
                  <th className="px-3 py-3 text-right">Exakt</th>
                  <th className="px-3 py-3 text-right">Beste Serie</th>
                </tr>
              </thead>
              <tbody>
                {(overview.data?.table ?? []).map((r) => (
                  <tr key={r.user.id} className={clsx("border-b border-white/5 last:border-0", r.user.id === me.id && "bg-gold/[0.08]")}>
                    <td className="px-4 py-2.5 font-bold text-slate-300">{r.rank}</td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <Avatar user={r.user} size={26} /> <span className="font-semibold text-white">{r.user.display_name}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right font-bold text-white tabular-nums">{r.points}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300 tabular-nums">{percent(r.hit_rate)}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300 tabular-nums">{r.correct_winners}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300 tabular-nums">{r.exact_scores}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300 tabular-nums">{r.best_streak}</td>
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
