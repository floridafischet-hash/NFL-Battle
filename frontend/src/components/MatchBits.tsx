"use client";

import clsx from "clsx";
import { Lock } from "lucide-react";

import { Badge } from "@/components/ui";
import { isLive } from "@/lib/bracket";
import type { Distribution, Match, Team } from "@/lib/types";

import { TeamLogo } from "./TeamLogo";

export function StatusBadge({ match }: { match: Pick<Match, "status" | "locked" | "kickoff_at"> }) {
  if (match.status === "FINAL") return <Badge tone="neutral">Final</Badge>;
  if (match.status === "VOID") return <Badge tone="amber">Annulliert</Badge>;
  if (isLive(match)) return <Badge tone="live">Live</Badge>;
  if (match.locked)
    return (
      <Badge tone="red">
        <Lock className="size-3" /> Gesperrt
      </Badge>
    );
  return <Badge tone="green">Offen</Badge>;
}

function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  return (0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
}

/** Team color that stays visible on the dark UI. */
export function barColor(team: Team): string {
  return luminance(team.primary_color) < 0.12 ? team.secondary_color : team.primary_color;
}

export function DistributionBar({ distribution, home, away }: { distribution: Distribution | null | undefined; home: Team | null; away: Team | null }) {
  if (!distribution || distribution.total === 0 || !home || !away) return null;
  const pct = (team: Team) => distribution.teams.find((t) => t.team_id === team.id)?.percent ?? 0;
  const h = pct(home);
  const a = pct(away);
  const other = Math.max(0, 100 - h - a);
  return (
    <div className="space-y-1" aria-label="Tippverteilung der Community">
      <div className="flex justify-between text-[11px] font-semibold">
        <span className="text-slate-200">
          {h} % {home.short_name}
        </span>
        <span className="text-slate-200">
          {away.short_name} {a} %
        </span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-white/5">
        <div style={{ width: `${h}%`, background: barColor(home) }} className="transition-all" />
        {other > 0 && <div style={{ width: `${other}%` }} className="bg-slate-600" title="ungültige Tipps" />}
        <div style={{ width: `${a}%`, background: barColor(away) }} className="ml-auto transition-all" />
      </div>
      <p className="text-[10px] text-slate-500">{distribution.total} Tipps</p>
    </div>
  );
}

export function TeamLine({ team, score, winner, size = 32, align = "left" }: { team: Team | null; score?: number | null; winner?: boolean; size?: number; align?: "left" | "right" }) {
  return (
    <div className={clsx("flex min-w-0 flex-1 items-center gap-2.5", align === "right" && "flex-row-reverse text-right", winner === false && "opacity-55")}>
      <TeamLogo team={team} size={size} glow={winner} />
      <div className="min-w-0">
        <p className={clsx("truncate font-semibold", winner ? "text-white" : "text-slate-200")}>{team?.short_name ?? "TBD"}</p>
        <p className="truncate text-[11px] text-slate-500">{team ? `Seed ${team.seed ?? "–"} · ${team.abbreviation}` : "noch offen"}</p>
      </div>
      {score != null && <span className={clsx("display ml-auto px-1 text-2xl font-bold tabular-nums", align === "right" && "mr-auto ml-0", winner ? "text-white" : "text-slate-500")}>{score}</span>}
    </div>
  );
}
