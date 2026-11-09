"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Activity, CalendarDays, HeartPulse, Search, Shield, Star, UsersRound } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge, Card, EmptyState, ErrorBox, Loading, Modal, PageHeader, Tabs } from "@/components/ui";
import { put } from "@/lib/api";
import { dateTime, kickoffShort } from "@/lib/format";
import { useLivePlayer, useLiveTeam, useLiveTeams } from "@/lib/queries";
import { useToast } from "@/lib/toast";
import type { LiveGame, LivePlayer, LiveTeam, LiveTeamsData } from "@/lib/types";

type Tab = "overview" | "injuries" | "roster" | "odds";

const POSITION_LABELS: Record<string, string> = {
  QB: "Quarterback", RB: "Running Back", FB: "Fullback", WR: "Wide Receiver", TE: "Tight End",
  OT: "Offensive Tackle", T: "Offensive Tackle", OG: "Offensive Guard", G: "Offensive Guard", C: "Center", OL: "Offensive Line",
  DE: "Defensive End", DT: "Defensive Tackle", NT: "Nose Tackle", DL: "Defensive Line",
  LB: "Linebacker", ILB: "Inside Linebacker", OLB: "Outside Linebacker", CB: "Cornerback",
  S: "Safety", FS: "Free Safety", SS: "Strong Safety", DB: "Defensive Back",
  K: "Kicker", P: "Punter", LS: "Long Snapper", KR: "Kick Returner", PR: "Punt Returner",
};

function positionLabel(position: string | null, fallback?: string | null) {
  if (!position) return fallback || "Position nicht angegeben";
  return `${POSITION_LABELS[position] || fallback || position} (${position})`;
}

function experienceLabel(value: string | null) {
  return value?.replace(/(\d+)(?:st|nd|rd|th) Season/i, "$1. Saison") ?? null;
}

function TeamLogo({ team, size = 64 }: { team: Pick<LiveTeam, "name" | "logo">; size?: number }) {
  return team.logo ? (
    // eslint-disable-next-line @next/next/no-img-element -- remote ESPN logos are dynamic
    <img src={team.logo} alt={team.name} width={size} height={size} className="object-contain" loading="lazy" />
  ) : (
    <div className="flex items-center justify-center text-slate-500" style={{ width: size, height: size }}><Shield /></div>
  );
}

function GameRow({ game }: { game: LiveGame }) {
  return (
    <div className="grid gap-2 rounded-xl border border-white/7 bg-white/[0.025] p-3 sm:grid-cols-[130px_1fr_auto] sm:items-center">
      <span className="text-xs text-slate-400">{kickoffShort(game.date)}</span>
      <div className="flex items-center gap-2">
        {game.opponent.logo && <img src={game.opponent.logo} alt="" className="size-7 object-contain" />}
        <span className="font-semibold text-white">{game.home_away === "home" ? "vs." : "@"} {game.opponent.name}</span>
      </div>
      <div className="flex items-center gap-2 sm:justify-end">
        {game.completed ? (
          <>
            <Badge tone={game.won ? "green" : "red"}>{game.won ? "Sieg" : "Niederlage"}</Badge>
            <span className="display text-lg font-bold text-white tabular-nums">{game.team_score}:{game.opponent_score}</span>
          </>
        ) : <Badge tone="neutral">{game.status || "Geplant"}</Badge>}
      </div>
    </div>
  );
}

function PlayerDetail({ athleteId, onClose }: { athleteId: string | null; onClose: () => void }) {
  const query = useLivePlayer(athleteId);
  const data = query.data;
  return <Modal open={!!athleteId} onClose={onClose} wide title={data?.player.name ?? "Spielerdaten werden geladen …"}>
    {query.isLoading && <Loading label="Aktuelle Spielerstatistiken werden geladen …" />}
    {query.error && <ErrorBox error={query.error} />}
    {data && <div className="space-y-5">
      <div className="flex items-center gap-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        {data.player.headshot ? <img src={data.player.headshot} alt="" className="size-24 rounded-xl bg-white/5 object-contain" /> : <UsersRound className="size-16 text-slate-500" />}
        <div className="min-w-0 flex-1">
          <p className="display text-2xl font-bold text-white">{data.player.jersey ? `#${data.player.jersey} ` : ""}{data.player.name}</p>
          <p className="font-semibold text-gold">{positionLabel(data.player.position, data.player.position_name)}</p>
          <p className="mt-1 text-xs text-slate-400">{[data.player.age ? `${data.player.age} Jahre` : null, data.player.height, data.player.weight, experienceLabel(data.player.experience)].filter(Boolean).join(" · ")}</p>
          <p className="mt-1 text-[11px] text-slate-500">Saison {data.season} · Stand: {dateTime(data.updated_at)} · Quelle: {data.source}</p>
        </div>
      </div>
      {data.summary.length > 0 && <section><h3 className="mb-2 font-semibold text-white">Aktuelle Saison auf einen Blick</h3><div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{data.summary.map((stat) => <div key={stat.key} className="rounded-xl border border-gold/15 bg-gold/5 p-3"><p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">{stat.label}</p><p className="display mt-1 text-xl font-bold text-white">{stat.value ?? "–"}</p></div>)}</div></section>}
      {data.categories.length ? data.categories.map((category) => <section key={category.key}><h3 className="mb-2 font-semibold text-white">{category.label}</h3><div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{category.stats.map((stat) => <div key={stat.key} className="rounded-xl border border-white/7 bg-black/20 p-3"><p className="text-[10px] font-semibold tracking-wide text-slate-500 uppercase">{stat.label}</p><p className="display mt-1 text-lg font-bold text-white">{stat.value}</p></div>)}</div></section>) : <EmptyState title="Keine Saisonstatistiken verfügbar">Für diesen Spieler meldet die Quelle aktuell keine Statistikwerte.</EmptyState>}
      {(data.player.college || data.player.draft) && <div className="rounded-xl border border-white/7 bg-white/[0.025] p-3 text-xs text-slate-400">{data.player.college && <p>College: <span className="text-white">{data.player.college}</span></p>}{data.player.draft && <p>Draft: <span className="text-white">{data.player.draft}</span></p>}</div>}
    </div>}
  </Modal>;
}

function TeamDetail({ slug, onClose, onPlayer }: { slug: string | null; onClose: () => void; onPlayer: (player: LivePlayer) => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const query = useLiveTeam(slug);
  const data = query.data;
  return (
    <Modal open={!!slug} onClose={onClose} wide title={data?.team.name ?? "Teamdaten werden geladen …"}>
      {query.isLoading && <Loading label="Aktuelle NFL-Daten werden geladen …" />}
      {query.error && <ErrorBox error={query.error} />}
      {data && (
        <div className="space-y-5">
          <div className="flex items-center gap-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
            <TeamLogo team={data.team} size={82} />
            <div className="min-w-0 flex-1">
              <p className="display text-2xl font-bold text-white">{data.team.name}</p>
              <p className="text-sm text-slate-400">{data.team.record || "Bilanz nicht verfügbar"}{data.team.standing ? ` · ${data.team.standing}` : ""}</p>
              <p className="mt-1 text-[11px] text-slate-500">Stand: {dateTime(data.updated_at)} · Quelle: {data.source}</p>
            </div>
          </div>

          <Tabs value={tab} onChange={setTab} tabs={[
            { value: "overview", label: "Überblick" },
            { value: "injuries", label: "Verletzte", badge: data.injuries.length },
            { value: "roster", label: "Kader" },
            { value: "odds", label: "Quoten" },
          ]} />

          {tab === "overview" && <div className="space-y-5">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {data.statistics.map((stat) => <div key={stat.key} className="rounded-xl border border-white/7 bg-black/20 p-3">
                <p className="text-[10px] font-semibold tracking-wide text-slate-500 uppercase">{stat.label}</p>
                <p className="display mt-1 text-xl font-bold text-white">{stat.value ?? "–"}</p>
              </div>)}
            </div>
            <section><h3 className="mb-2 flex items-center gap-2 font-semibold text-white"><Activity className="size-4 text-gold" /> Letzte 5 Spiele</h3>
              <div className="space-y-2">{data.last_games.length ? data.last_games.map((g) => <GameRow key={g.id} game={g} />) : <EmptyState title="Noch keine abgeschlossenen Spiele" />}</div>
            </section>
            <section><h3 className="mb-2 flex items-center gap-2 font-semibold text-white"><CalendarDays className="size-4 text-gold" /> Nächste Spiele</h3>
              <div className="space-y-2">{data.upcoming_games.length ? data.upcoming_games.map((g) => <GameRow key={g.id} game={g} />) : <EmptyState title="Keine kommenden Spiele veröffentlicht" />}</div>
            </section>
          </div>}

          {tab === "injuries" && <div className="space-y-2">{data.injuries.length ? data.injuries.map((injury) => (
            <div key={injury.id} className="flex items-center gap-3 rounded-xl border border-white/7 bg-white/[0.025] p-3">
              {injury.headshot ? <img src={injury.headshot} alt="" className="size-11 rounded-full bg-white/5 object-contain" /> : <HeartPulse className="size-8 text-red-300" />}
              <div className="min-w-0 flex-1"><p className="font-semibold text-white">{injury.name} <span className="text-xs text-slate-500">{injury.position}</span></p><p className="text-xs text-slate-400">{injury.detail || "Keine nähere Angabe"}{injury.return_date ? ` · mögliche Rückkehr ${kickoffShort(injury.return_date)}` : ""}</p></div>
              <Badge tone={/out|reserve|susp/i.test(injury.status) ? "red" : "amber"}>{injury.status}</Badge>
            </div>
          )) : <EmptyState icon={<HeartPulse />} title="Keine Verletzungen gemeldet">Die Quelle meldet aktuell keine Ausfälle.</EmptyState>}</div>}

          {tab === "roster" && <div className="space-y-5">{data.roster.map((group) => <section key={group.key}><h3 className="mb-2 flex items-center gap-2 font-semibold text-white"><UsersRound className="size-4 text-gold" /> {group.label} <span className="text-xs text-slate-500">({group.players.length})</span></h3><div className="grid gap-2 sm:grid-cols-2">{group.players.map((player) => <button type="button" onClick={() => onPlayer(player)} key={player.id} className="focus-ring flex items-center gap-3 rounded-xl border border-white/7 bg-white/[0.025] p-2.5 text-left transition hover:border-gold/25 hover:bg-gold/5">{player.headshot ? <img src={player.headshot} alt="" className="size-11 rounded-full bg-white/5 object-contain" /> : <div className="size-11 rounded-full bg-white/5" />}<div className="min-w-0"><p className="truncate font-semibold text-white">{player.jersey ? `#${player.jersey} ` : ""}{player.name}</p><p className="truncate text-xs font-medium text-gold/90">{positionLabel(player.position, player.position_name)}</p><p className="text-[11px] text-slate-500">{player.age ? `${player.age} Jahre` : "Alter –"} · {player.experience ?? 0}. Jahr · Statistiken öffnen</p></div></button>)}</div></section>)}</div>}

          {tab === "odds" && (data.odds ? <div className="space-y-4">
            <div className="rounded-2xl border border-gold/20 bg-gold/5 p-4"><p className="text-xs font-semibold tracking-wide text-gold uppercase">Nächstes Spiel · {data.odds.provider || "Anbieter"}</p><p className="display mt-1 text-xl font-bold text-white">vs. {data.odds.opponent}</p><p className="text-sm text-slate-400">{kickoffShort(data.odds.date)}</p></div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{[["Spread", data.odds.details], ["Over/Under", data.odds.over_under], [data.team.abbreviation, data.odds.team_moneyline], ["Gegner", data.odds.opponent_moneyline]].map(([label,value]) => <div key={String(label)} className="rounded-xl border border-white/7 bg-black/20 p-3 text-center"><p className="text-[10px] font-semibold text-slate-500 uppercase">{label}</p><p className="display mt-1 text-xl font-bold text-white">{value ?? "–"}</p></div>)}</div>
            <p className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-200">Quoten sind Momentaufnahmen, können regional fehlen und sich jederzeit ändern. Keine Wettberatung.</p>
          </div> : <EmptyState title="Keine aktuellen Quoten verfügbar">Für das nächste Spiel liefert die Datenquelle momentan keine Quoten.</EmptyState>)}
        </div>
      )}
    </Modal>
  );
}

export default function TeamsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const teams = useLiveTeams();
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedPlayer, setSelectedPlayer] = useState<LivePlayer | null>(null);
  const [search, setSearch] = useState("");
  const favorites = teams.data?.favorites ?? [];
  const favoriteSet = useMemo(() => new Set(favorites), [favorites]);
  const filtered = useMemo(() => (teams.data?.teams ?? [])
    .filter((team) => `${team.name} ${team.abbreviation}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const favoriteOrder = (favoriteSet.has(a.slug) ? 0 : 1) - (favoriteSet.has(b.slug) ? 0 : 1);
      return favoriteOrder || a.name.localeCompare(b.name, "de");
    }), [teams.data, search, favoriteSet]);
  const saveFavorites = useMutation({
    mutationFn: (next: string[]) => put<{ favorites: string[] }>("/api/live/teams/favorites", { favorites: next }),
    onSuccess: ({ favorites: saved }) => {
      queryClient.setQueryData<LiveTeamsData>(
        ["live-nfl", "teams"],
        (current) => current ? { ...current, favorites: saved } : current,
      );
      toast.success("Favoriten gespeichert", "Die Auswahl gilt nur für dein Benutzerkonto.");
    },
    onError: (error) => toast.error("Favoriten nicht gespeichert", error instanceof Error ? error.message : "Unbekannter Fehler"),
  });
  const toggleFavorite = (slug: string) => {
    const next = favoriteSet.has(slug) ? favorites.filter((item) => item !== slug) : [...favorites, slug];
    saveFavorites.mutate(next);
  };
  return <div>
    <PageHeader title="NFL Teams" subtitle="Aktuelle Mannschaften, Form, Kader, Verletzungen und Quoten" />
    <p className="mb-4 text-xs text-slate-400">Mit dem Stern legst du deine persönlichen Favoriten fest. Sie werden nur in deinem Konto gespeichert und immer zuerst angezeigt.</p>
    {teams.isLoading && <Loading label="Aktuelle NFL-Teams werden geladen …" />}
    {teams.error && <ErrorBox error={teams.error} />}
    <main className="min-w-0" aria-label="NFL Teams">
      <div className="relative mb-5"><Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-500" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Team suchen …" className="focus-ring h-11 w-full rounded-xl border border-white/10 bg-white/5 pr-4 pl-10 text-sm text-white placeholder:text-slate-500 sm:max-w-xl" /></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{filtered.map((team) => {
      const favorite = favoriteSet.has(team.slug);
      return <Card key={team.id} className={clsx("group relative h-full transition hover:-translate-y-0.5 hover:border-white/15", favorite && "border-gold/60 bg-gold/[0.12] shadow-[0_0_24px_rgba(214,179,90,0.08)]")} bodyClassName="flex items-center gap-3 p-3.5">
        <button onClick={() => setSelected(team.slug)} className="focus-ring flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left" aria-label={`${team.name} Details öffnen`}>
          <TeamLogo team={team} size={44} />
          <div className="min-w-0"><p className="display truncate text-base font-bold text-white">{team.name}</p><p className="truncate text-[11px] font-semibold text-slate-500">{team.abbreviation} · Details öffnen</p></div>
        </button>
        <button
          type="button"
          onClick={() => toggleFavorite(team.slug)}
          disabled={saveFavorites.isPending}
          aria-label={favorite ? `${team.name} aus Favoriten entfernen` : `${team.name} zu Favoriten hinzufügen`}
          title={favorite ? "Favorit entfernen" : "Als Favorit markieren"}
          className={clsx("focus-ring rounded-lg p-2 transition hover:bg-white/10", favorite ? "text-gold" : "text-slate-500")}
        ><Star className={clsx("size-4", favorite && "fill-current")} /></button>
      </Card>;
      })}</div>
      {!teams.isLoading && !filtered.length && <EmptyState title="Kein Team gefunden" />}
    </main>
    <TeamDetail slug={selectedPlayer ? null : selected} onClose={() => setSelected(null)} onPlayer={setSelectedPlayer} />
    <PlayerDetail athleteId={selectedPlayer?.id ?? null} onClose={() => setSelectedPlayer(null)} />
  </div>;
}
