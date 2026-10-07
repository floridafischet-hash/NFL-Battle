"use client";

import clsx from "clsx";
import { ArrowDown, ArrowRight, ArrowUp, Minus, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { TeamLogo } from "@/components/TeamLogo";
import { Button, Card, EmptyState } from "@/components/ui";
import { slotLabel } from "@/lib/bracket";
import { countdown, dateLong, timeOnly } from "@/lib/format";
import type { DashboardData, LeaderboardRow, Match, Tip } from "@/lib/types";

function CountdownBox({ target }: { target: string | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const c = countdown(target, now);
  if (!target) return <p className="text-center text-sm text-slate-400">Kickoff-Termin folgt</p>;
  if (c.done) {
    return (
      <p className="flex items-center justify-center gap-2 text-sm font-bold text-red-400">
        <span className="size-2 animate-pulse rounded-full bg-red-500" /> Das Spiel läuft
      </p>
    );
  }
  const parts = [
    { v: c.days, l: "Tage" },
    { v: c.hours, l: "Std" },
    { v: c.minutes, l: "Min" },
    { v: c.seconds, l: "Sek" },
  ];
  return (
    <div className="grid grid-cols-4 gap-2" aria-label="Countdown bis zum Kickoff">
      {parts.map((p) => (
        <div key={p.l} className="rounded-xl border border-white/8 bg-black/30 py-2 text-center">
          <p className="display text-2xl font-bold text-white tabular-nums">{String(p.v).padStart(2, "0")}</p>
          <p className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase">{p.l}</p>
        </div>
      ))}
    </div>
  );
}

export function NextGameCard({ match }: { match: (Match & { my_pick: Tip | null }) | null | undefined }) {
  if (!match || !match.home_team || !match.away_team) {
    return (
      <Card title="Nächstes Spiel" accent="gold">
        <EmptyState title="Kein Spiel angesetzt">Sobald die nächste Paarung feststeht, erscheint sie hier.</EmptyState>
      </Card>
    );
  }
  const pickTeam = match.my_pick ? [match.home_team, match.away_team].find((t) => t?.id === match.my_pick?.winner_team_id) : null;
  const team = (t: NonNullable<Match["home_team"]>, conf: string) => (
    <div className="flex min-w-0 flex-1 flex-col items-center gap-2 text-center">
      <div className="relative">
        <div className="absolute inset-0 rounded-full blur-xl" style={{ background: `${t.primary_color}66` }} />
        <TeamLogo team={t} size={76} className="relative" />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-bold tracking-widest text-slate-500">
          {conf} · SEED {t.seed ?? "–"}
        </p>
        <p className="display truncate text-lg leading-tight font-bold text-white">{t.short_name}</p>
        <p className="truncate text-[11px] text-slate-400">{t.city}</p>
      </div>
    </div>
  );
  const conf = match.conference ?? "SB";
  return (
    <Card
      title="Nächstes Spiel"
      accent={match.conference === "AFC" ? "afc" : match.conference === "NFC" ? "nfc" : "gold"}
      action={<span className="text-[11px] font-semibold text-slate-400">{slotLabel(match.slot)}</span>}
    >
      <div className="flex items-center gap-2">
        {team(match.home_team, conf)}
        <div className="display shrink-0 text-2xl font-bold text-slate-500">VS</div>
        {team(match.away_team, conf)}
      </div>
      <div className="mt-4 space-y-1 text-center">
        <p className="text-sm font-semibold text-slate-200">{dateLong(match.kickoff_at)}</p>
        <p className="text-xs text-slate-400">
          {timeOnly(match.kickoff_at)}
          {match.venue ? ` · ${match.venue}` : ""}
        </p>
      </div>
      <div className="mt-4">
        <CountdownBox target={match.kickoff_at} />
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="text-xs text-slate-400">
          {pickTeam ? (
            <span className="flex items-center gap-1.5">
              Dein Tipp: <TeamLogo team={pickTeam} size={20} />{" "}
              <strong className="text-white">{pickTeam.short_name}</strong>
              {match.my_pick?.winner_score != null && (
                <span className="tabular-nums">
                  ({match.my_pick.winner_score}:{match.my_pick.loser_score})
                </span>
              )}
            </span>
          ) : (
            <span className="text-amber-300">Noch kein Tipp!</span>
          )}
        </div>
        <Link href={`/spiele/${match.id}`}>
          <Button variant="primary" size="sm">
            Zum Spiel <ArrowRight className="size-4" />
          </Button>
        </Link>
      </div>
    </Card>
  );
}

export function UserStatsCard({ me }: { me: NonNullable<DashboardData["me"]> }) {
  const tiles = [
    { label: "Gesamtpunkte", value: me.points, tone: "text-gold" },
    { label: "Richtige Tipps", value: `${me.correct_winners} / ${me.total_final_matches}` },
    { label: "Exakte Ergebnisse", value: me.exact_scores },
    { label: "Richtiger Champion", value: me.champion_correct ? 1 : 0 },
  ];
  return (
    <Card title="Deine Saison" accent="gold">
      <div className="flex items-center gap-4">
        <div className="relative flex size-20 shrink-0 flex-col items-center justify-center rounded-2xl bg-gradient-to-br from-gold/25 to-transparent ring-1 ring-gold/30">
          <span className="text-[10px] font-bold tracking-widest text-gold">RANG</span>
          <span className="display text-3xl leading-none font-bold text-white">{me.rank ?? "–"}</span>
          <span className="text-[10px] text-slate-400">von {me.participants}</span>
        </div>
        <div className="min-w-0">
          <p className="display text-2xl font-bold text-white">{me.display_name}</p>
          <p className="text-sm text-slate-400">
            {me.missing_open_picks > 0 ? (
              <span className="text-amber-300">{me.missing_open_picks} offene Tipps</span>
            ) : (
              "Alle offenen Spiele getippt ✓"
            )}
          </p>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-2">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-xl border border-white/6 bg-white/[0.03] px-3 py-2">
            <dt className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase">{t.label}</dt>
            <dd className={clsx("display text-xl font-bold", t.tone ?? "text-white")}>{t.value}</dd>
          </div>
        ))}
      </dl>
      <Link href="/bracket" className="mt-4 block">
        <Button variant="secondary" className="w-full">
          Mein Bracket anzeigen <ArrowRight className="size-4" />
        </Button>
      </Link>
    </Card>
  );
}

export function Trend({ row }: { row: Pick<LeaderboardRow, "rank" | "previous_rank"> }) {
  if (row.previous_rank == null || row.previous_rank === row.rank)
    return <Minus className="size-3.5 text-slate-600" aria-label="unverändert" />;
  return row.previous_rank > row.rank ? (
    <ArrowUp className="size-3.5 text-emerald-400" aria-label="aufgestiegen" />
  ) : (
    <ArrowDown className="size-3.5 text-red-400" aria-label="abgestiegen" />
  );
}

export function LeaderboardCompact({ rows }: { rows: LeaderboardRow[] }) {
  return (
    <Card
      title="Rangliste"
      action={
        <Link href="/rangliste" className="text-xs font-semibold text-gold hover:underline">
          Alle
        </Link>
      }
      bodyClassName="p-2 sm:p-3"
    >
      {rows.length === 0 ? (
        <EmptyState title="Noch keine Punkte" />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] tracking-wider text-slate-500 uppercase">
              <th className="px-2 py-1 text-left font-semibold">#</th>
              <th className="px-2 py-1 text-left font-semibold">Spieler</th>
              <th className="px-1 py-1 text-right font-semibold" title="Richtige Sieger">✓</th>
              <th className="px-1 py-1 text-right font-semibold" title="Exakte Ergebnisse">🎯</th>
              <th className="px-2 py-1 text-right font-semibold">Pkt</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.user.id} className={clsx("rounded-lg", r.is_me && "bg-gold/10")}>
                <td className="px-2 py-1.5">
                  <span className="flex items-center gap-1">
                    <span className={clsx("display w-5 font-bold", r.rank === 1 ? "text-gold" : "text-slate-400")}>{r.rank}</span>
                    <Trend row={r} />
                  </span>
                </td>
                <td className="px-2 py-1.5">
                  <span className="flex items-center gap-2">
                    <Avatar user={r.user} size={24} ring={r.is_me} />
                    <span className={clsx("truncate font-semibold", r.is_me ? "text-gold" : "text-slate-100")}>{r.user.display_name}</span>
                    {r.rank === 1 && <Trophy className="size-3.5 text-gold" />}
                  </span>
                </td>
                <td className="px-1 py-1.5 text-right text-slate-400 tabular-nums">{r.correct_winners}</td>
                <td className="px-1 py-1.5 text-right text-slate-400 tabular-nums">{r.exact_scores}</td>
                <td className="display px-2 py-1.5 text-right text-base font-bold text-white tabular-nums">{r.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export function RecentResults({ matches }: { matches: Match[] }) {
  return (
    <Card
      title="Letzte Ergebnisse"
      action={
        <Link href="/spiele" className="text-xs font-semibold text-gold hover:underline">
          Alle Spiele
        </Link>
      }
      bodyClassName="p-2 sm:p-3"
    >
      {matches.length === 0 ? (
        <EmptyState title="Noch keine Ergebnisse" />
      ) : (
        <ul className="space-y-1.5">
          {matches.map((m) => {
            const homeWon = m.winner_team_id === m.home_team?.id;
            return (
              <li key={m.id}>
                <Link href={`/spiele/${m.id}`} className="flex items-center gap-2 rounded-xl px-2 py-2 hover:bg-white/5">
                  <span className={clsx("flex min-w-0 flex-1 items-center gap-2", !homeWon && "opacity-50")}>
                    <TeamLogo team={m.home_team} size={26} />
                    <span className={clsx("truncate text-sm", homeWon ? "font-bold text-white" : "text-slate-400")}>{m.home_team?.short_name}</span>
                  </span>
                  <span className="display shrink-0 text-lg font-bold tabular-nums">
                    <span className={homeWon ? "text-white" : "text-slate-500"}>{m.home_score}</span>
                    <span className="mx-1 text-slate-600">:</span>
                    <span className={!homeWon ? "text-white" : "text-slate-500"}>{m.away_score}</span>
                  </span>
                  <span className={clsx("flex min-w-0 flex-1 items-center justify-end gap-2", homeWon && "opacity-50")}>
                    <span className={clsx("truncate text-right text-sm", !homeWon ? "font-bold text-white" : "text-slate-400")}>{m.away_team?.short_name}</span>
                    <TeamLogo team={m.away_team} size={26} />
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
