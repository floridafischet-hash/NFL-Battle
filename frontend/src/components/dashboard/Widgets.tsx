"use client";

import clsx from "clsx";
import { Activity, ArrowDown, ArrowRight, ArrowUp, CalendarDays, ChevronDown, Maximize2, Minus, Star, Trophy } from "lucide-react";
import Link from "next/link";
import { Fragment, useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, EmptyState, Loading } from "@/components/ui";
import { slotLabel } from "@/lib/bracket";
import { countdown, dateLong, dateTime, kickoffShort, timeOnly } from "@/lib/format";
import { useLiveGames } from "@/lib/queries";
import type { DashboardData, LeaderboardRow, LiveScoreboardGame, LiveScoreboardTeam, Match, Tip } from "@/lib/types";

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

function ScoreboardTeam({ team, gameState }: { team: LiveScoreboardTeam; gameState: LiveScoreboardGame["state"] }) {
  return <div className="flex min-w-0 items-center gap-2">
    {team.logo ? <img src={team.logo} alt="" className="size-8 shrink-0 object-contain" /> : <div className="size-8 shrink-0" />}
    <div className="min-w-0 flex-1">
      <p className={clsx("truncate text-xs font-semibold", team.winner ? "text-white" : "text-slate-300")}>{team.short_name || team.name}</p>
      {team.record && <p className="text-[10px] text-slate-500">{team.record}</p>}
    </div>
    {gameState !== "pre" && <span className={clsx("display text-lg font-bold tabular-nums", team.winner ? "text-gold" : "text-white")}>{team.score ?? "–"}</span>}
  </div>;
}

export function ScoreboardGame({ game, favorite = false }: { game: LiveScoreboardGame; favorite?: boolean }) {
  const live = game.state === "in";
  return <div className={clsx("relative rounded-xl border p-3 transition-colors", favorite ? "border-gold/45 bg-gold/[0.09] shadow-[inset_3px_0_0_#d6b35a]" : live ? "border-red-500/25 bg-red-500/[0.06]" : "border-white/7 bg-white/[0.025]")}>
    <div className="mb-2 flex items-center justify-between gap-2">
      <span className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-400">{favorite && <Star className="size-3 fill-gold text-gold" aria-label="Favoritenteam beteiligt" />}{kickoffShort(game.date)}</span>
      {live ? <Badge tone="red"><span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-current" /> LIVE · {game.status}</Badge> : game.completed ? <Badge tone="neutral">Endstand</Badge> : <Badge tone="neutral">Geplant</Badge>}
    </div>
    <div className="space-y-1.5">
      <ScoreboardTeam team={game.away} gameState={game.state} />
      <ScoreboardTeam team={game.home} gameState={game.state} />
    </div>
  </div>;
}

export function DashboardCountdown() {
  const query = useLiveGames();
  const nextGame = query.data?.games.find((game) => game.state === "pre");
  if (!nextGame) return null;
  return <details className="group glass mx-auto w-full max-w-2xl rounded-2xl border border-gold/20" open>
    <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-4 py-3 [&::-webkit-details-marker]:hidden">
      <span className="min-w-0">
        <span className="block text-[10px] font-bold tracking-[0.22em] text-gold uppercase">Nächster Kickoff</span>
        <span className="display block truncate text-sm font-bold text-white sm:text-base">{nextGame.away.short_name} @ {nextGame.home.short_name}</span>
      </span>
      <ChevronDown className="size-5 shrink-0 text-slate-400 transition-transform group-open:rotate-180" aria-hidden="true" />
    </summary>
    <div className="border-t border-white/5 px-4 py-3">
      <CountdownBox target={nextGame.date} />
    </div>
  </details>;
}

export function FavoriteStandingsCard() {
  const query = useLiveGames();
  if (query.isLoading) return <Card title="Meine NFL-Teams"><Loading label="Platzierungen werden geladen …" /></Card>;
  const rows = query.data?.favorite_standings ?? [];
  return <Card title={<span className="flex items-center gap-2"><Star className="size-4 fill-gold text-gold" /> Meine NFL-Teams</span>} action={<Link href="/teams" className="text-xs font-semibold text-gold hover:underline">Bearbeiten</Link>} bodyClassName="p-2 sm:p-3">
    {rows.length === 0 ? <EmptyState title="Noch keine Favoriten">Wähle auf der Teams-Seite deine NFL-Favoriten aus.</EmptyState> : <div className="divide-y divide-white/5">
      {rows.map((row) => <Link key={row.slug} href={`/teams?team=${row.slug}`} className="focus-ring flex items-center gap-3 rounded-lg px-2 py-2.5 transition hover:bg-white/5">
        {row.logo ? <img src={row.logo} alt="" className="size-8 shrink-0 object-contain" /> : <div className="size-8" />}
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-white">{row.name}</span>
        {row.record && <span className="text-xs tabular-nums text-slate-500">{row.record}</span>}
        <Badge tone={row.conference === "AFC" ? "afc" : "nfc"}>{row.conference} · {row.rank}.</Badge>
      </Link>)}
    </div>}
  </Card>;
}

export function scoreboardGroup(game: LiveScoreboardGame): "live" | "upcoming" | "completed" {
  if (game.state === "in") return "live";
  if (game.state === "pre") return "upcoming";
  return "completed";
}

const SCOREBOARD_GROUP_LABELS = {
  live: "Jetzt live",
  upcoming: "Als Nächstes",
  completed: "Letzte Ergebnisse",
};

export function CurrentGamesCard({ fallback }: { fallback: (Match & { my_pick: Tip | null }) | null | undefined }) {
  const query = useLiveGames();
  if (query.isLoading) return <Card title="Aktuelle NFL-Spiele" accent="gold"><Loading label="Spielplan wird geladen …" /></Card>;
  const data = query.data;
  if (query.error || !data?.regular_season || !data.games.length) return <NextGameCard match={fallback} />;
  const liveCount = data.games.filter((game) => game.state === "in").length;
  return <Card
    title={<span className="flex items-center gap-2">{liveCount ? <Activity className="size-4 text-red-400" /> : <CalendarDays className="size-4 text-gold" />} Aktuelle NFL-Spiele</span>}
    accent="gold"
    action={<div className="flex items-center gap-3"><span className="text-[11px] font-semibold text-slate-400">Woche {data.week ?? "–"}</span><Link href="/aktuelle-spiele" className="flex items-center gap-1 text-xs font-semibold text-gold hover:underline">Vollbild <Maximize2 className="size-3.5" /></Link></div>}
    bodyClassName="p-0"
  >
    <div className="scrollbar-thin max-h-[520px] space-y-2 overflow-y-auto p-4">
      {data.games.map((game, index) => {
        const group = scoreboardGroup(game);
        const previous = index > 0 ? scoreboardGroup(data.games[index - 1]) : null;
        return <Fragment key={game.id}>
          {group !== previous && <p className={clsx("pt-1 text-[10px] font-bold tracking-[0.18em] uppercase", group === "live" ? "text-red-400" : group === "upcoming" ? "text-gold" : "text-slate-500")}>{SCOREBOARD_GROUP_LABELS[group]}</p>}
          <ScoreboardGame game={game} favorite={data.favorites.some((slug) => [game.home.abbreviation, game.away.abbreviation].some((abbr) => abbr?.toLowerCase() === slug))} />
        </Fragment>;
      })}
    </div>
    <div className="border-t border-white/5 px-4 py-2 text-[10px] text-slate-500">Stand: {dateTime(data.updated_at)} · Quelle: {data.source} · Aktualisierung jede Minute</div>
  </Card>;
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
