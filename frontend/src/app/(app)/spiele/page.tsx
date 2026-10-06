"use client";

import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DistributionBar, StatusBadge, TeamLine } from "@/components/MatchBits";
import { TeamLogo } from "@/components/TeamLogo";
import { Card, EmptyState, Loading, PageHeader, Select } from "@/components/ui";
import { ROUND_TITLES, slotLabel } from "@/lib/bracket";
import { kickoffShort } from "@/lib/format";
import { useSeasonMatches, useSelectedSeason } from "@/lib/queries";
import type { Round, SeasonMatch } from "@/lib/types";

const ROUNDS: Round[] = ["WILD_CARD", "DIVISIONAL", "CONFERENCE", "SUPER_BOWL"];

function MatchRow({ m }: { m: SeasonMatch }) {
  const final = m.status === "FINAL";
  const pickTeam = m.my_pick ? [m.home_team, m.away_team].find((t) => t?.id === m.my_pick?.winner_team_id) : undefined;
  return (
    <Link
      href={`/spiele/${m.id}`}
      className="group grid gap-3 rounded-2xl border border-white/6 bg-white/[0.02] p-3 transition hover:border-white/15 hover:bg-white/[0.05] sm:p-4 lg:grid-cols-[minmax(0,1fr)_200px_220px_24px] lg:items-center"
    >
      <div className="flex items-center gap-3">
        <TeamLine team={m.home_team} score={final ? m.home_score : null} winner={final ? m.winner_team_id === m.home_team?.id : undefined} />
        <span className="display shrink-0 text-sm font-bold text-slate-600">VS</span>
        <TeamLine team={m.away_team} score={final ? m.away_score : null} winner={final ? m.winner_team_id === m.away_team?.id : undefined} align="right" />
      </div>
      <div className="flex items-center justify-between gap-2 text-xs text-slate-400 lg:flex-col lg:items-start">
        <span className="flex items-center gap-2">
          <StatusBadge match={m} />
          <span className={clsx("font-semibold", m.conference === "AFC" ? "text-afc-soft" : m.conference === "NFC" ? "text-nfc-soft" : "text-gold")}>
            {slotLabel(m.slot)}
          </span>
        </span>
        <span>{kickoffShort(m.kickoff_at)}</span>
      </div>
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          Dein Tipp:
          {pickTeam ? (
            <span className="flex items-center gap-1.5 font-semibold text-white">
              <TeamLogo team={pickTeam} size={18} /> {pickTeam.short_name}
              {m.my_pick?.winner_score != null && (
                <span className="text-slate-400 tabular-nums">
                  {m.my_pick.winner_score}:{m.my_pick.loser_score}
                </span>
              )}
            </span>
          ) : (
            <span className={m.locked ? "text-slate-500" : "text-amber-300"}>{m.home_team && m.away_team ? "–" : "Paarung offen"}</span>
          )}
          {m.my_points != null && (
            <span className={clsx("ml-auto rounded px-1.5 font-bold", m.my_points > 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-white/5 text-slate-500")}>
              +{m.my_points}
            </span>
          )}
        </div>
        <DistributionBar distribution={m.distribution} home={m.home_team} away={m.away_team} />
      </div>
      <ChevronRight className="hidden size-5 text-slate-600 group-hover:text-white lg:block" />
    </Link>
  );
}

export default function MatchesPage() {
  const [selected, setSelected] = useState<number | null>(null);
  const { id, seasons, season } = useSelectedSeason(selected);
  const matches = useSeasonMatches(id);

  return (
    <div>
      <PageHeader title="Spiele" subtitle={season ? `Alle Playoff-Spiele der Saison ${season.name}` : undefined}>
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
      {matches.isLoading && <Loading />}
      {!matches.isLoading && !matches.data?.length && (
        <Card>
          <EmptyState title="Keine Spiele" />
        </Card>
      )}
      <div className="space-y-6">
        {ROUNDS.map((round) => {
          const list = (matches.data ?? []).filter((m) => m.round === round);
          if (!list.length) return null;
          return (
            <Card key={round} title={ROUND_TITLES[round]} accent={round === "SUPER_BOWL" ? "gold" : undefined} bodyClassName="space-y-2 p-2 sm:p-3">
              {list.map((m) => (
                <MatchRow key={m.id} m={m} />
              ))}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
