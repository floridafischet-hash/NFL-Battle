"use client";

import { Activity, CalendarDays, CheckCircle2, Clock3 } from "lucide-react";

import { scoreboardGroup, ScoreboardGame } from "@/components/dashboard/Widgets";
import { Card, EmptyState, ErrorBox, Loading, PageHeader, StatTile } from "@/components/ui";
import { dateTime } from "@/lib/format";
import { useLiveGames } from "@/lib/queries";

export default function CurrentGamesPage() {
  const query = useLiveGames();
  if (query.isLoading) return <Loading label="Aktuelle NFL-Spiele werden geladen …" />;
  if (query.error) return <ErrorBox error={query.error} />;
  const data = query.data;
  const completed = data?.games.filter((game) => game.completed).length ?? 0;
  const live = data?.games.filter((game) => game.state === "in").length ?? 0;
  const upcoming = data?.games.filter((game) => game.state === "pre").length ?? 0;
  const groups = data ? [
    { key: "live", label: "Jetzt live", games: data.games.filter((game) => scoreboardGroup(game) === "live") },
    { key: "upcoming", label: "Als Nächstes", games: data.games.filter((game) => scoreboardGroup(game) === "upcoming") },
    { key: "completed", label: "Letzte Ergebnisse", games: data.games.filter((game) => scoreboardGroup(game) === "completed") },
  ].filter((group) => group.games.length) : [];

  return <div className="space-y-5">
    <PageHeader
      title="Aktuelle NFL-Spiele"
      subtitle={data?.regular_season ? `Regular Season ${data.season ?? ""} · Woche ${data.week ?? "–"}` : "Aktuell läuft keine Regular-Season-Woche"}
    />

    {data?.regular_season && data.games.length ? <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Spiele der Woche" value={data.games.length} tone="gold" />
        <StatTile label="Beendet" value={completed} tone="green" />
        <StatTile label="Live" value={live} tone={live ? "afc" : undefined} />
        <StatTile label="Noch offen" value={upcoming} />
      </div>

      <Card
        title={<span className="flex items-center gap-2">{live ? <Activity className="size-4 text-red-400" /> : <CalendarDays className="size-4 text-gold" />} Alle Spiele · Woche {data.week ?? "–"}</span>}
        action={<span className="text-xs text-slate-400">Aktualisierung jede Minute</span>}
      >
        <div className="space-y-6">
          {groups.map((group) => <section key={group.key}>
            <h3 className={group.key === "live" ? "mb-3 text-sm font-bold text-red-400" : group.key === "upcoming" ? "mb-3 text-sm font-bold text-gold" : "mb-3 text-sm font-bold text-slate-400"}>{group.label}</h3>
            <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
              {group.games.map((game) => <ScoreboardGame key={game.id} game={game} favorite={data.favorites.some((slug) => [game.home.abbreviation, game.away.abbreviation].some((abbr) => abbr?.toLowerCase() === slug))} />)}
            </div>
          </section>)}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/5 pt-3 text-xs text-slate-500">
          <span className="flex items-center gap-1.5"><CheckCircle2 className="size-3.5" /> Endstände und Ergebnisse</span>
          <span className="flex items-center gap-1.5"><Clock3 className="size-3.5" /> Zeiten für Europe/Berlin</span>
          <span>Stand: {dateTime(data.updated_at)} · Quelle: {data.source}</span>
        </div>
      </Card>
    </> : <Card><EmptyState title="Keine Regular-Season-Spiele">Während der Playoffs findest du die relevanten Partien wieder im Playoff-Bracket auf der Startseite.</EmptyState></Card>}
  </div>;
}
