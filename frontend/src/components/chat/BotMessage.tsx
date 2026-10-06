"use client";

import clsx from "clsx";
import { Lock, Trophy } from "lucide-react";

import { TeamLogo } from "@/components/TeamLogo";
import { kickoffShort } from "@/lib/format";
import type { ChatMessage } from "@/lib/types";


const TYPE_LABEL: Record<string, { label: string; tone: string }> = {
  FINAL: { label: "Final", tone: "bg-white text-ink-950" },
  CORRECTION: { label: "Korrektur", tone: "bg-amber-400 text-ink-950" },
  KICKOFF: { label: "Kickoff", tone: "bg-red-600 text-white" },
  HALFTIME: { label: "Halbzeit", tone: "bg-sky-500 text-white" },
  NEXT_ROUND: { label: "Nächste Runde", tone: "bg-gold text-ink-950" },
  MATCHUP: { label: "Paarungen", tone: "bg-gold text-ink-950" },
  OPEN_PICKS: { label: "Offene Tipps", tone: "bg-orange-500 text-white" },
  CHAMPION: { label: "Champion", tone: "bg-gradient-to-r from-gold to-gold-soft text-ink-950" },
  LEADERBOARD: { label: "Rangliste", tone: "bg-nfc text-white" },
  INFO: { label: "Info", tone: "bg-slate-600 text-white" },
};

function Scoreline({ match, compact }: { match: any; compact?: boolean }) {
  if (!match?.home || !match?.away) return null;
  const size = compact ? 28 : 36;
  const homeWon = match.winner_team_id === match.home.id;
  const awayWon = match.winner_team_id === match.away.id;
  const hasScore = match.home_score != null && match.away_score != null;
  return (
    <div className="flex items-center justify-between gap-2 rounded-xl bg-black/30 px-3 py-2">
      <div className={clsx("flex min-w-0 items-center gap-2", awayWon && "opacity-55")}>
        <TeamLogo team={match.home} size={size} glow={homeWon} />
        <span className={clsx("truncate font-semibold", compact ? "text-xs" : "text-sm")}>{match.home.short_name}</span>
      </div>
      <span className={clsx("display shrink-0 font-bold text-white tabular-nums", compact ? "text-lg" : "text-2xl")}>
        {hasScore ? `${match.home_score} : ${match.away_score}` : "vs"}
      </span>
      <div className={clsx("flex min-w-0 items-center justify-end gap-2", homeWon && "opacity-55")}>
        <span className={clsx("truncate text-right font-semibold", compact ? "text-xs" : "text-sm")}>{match.away.short_name}</span>
        <TeamLogo team={match.away} size={size} glow={awayWon} />
      </div>
    </div>
  );
}

export function BotMessage({ message, compact }: { message: ChatMessage; compact?: boolean }) {
  const sys = message.system;
  const type = sys?.type ?? "INFO";
  const payload = sys?.payload ?? {};
  const meta = TYPE_LABEL[type] ?? TYPE_LABEL.INFO;
  const lines = message.body.split("\n");

  let content: React.ReactNode;
  if ((type === "FINAL" || type === "CORRECTION") && payload.match && !payload.reset) {
    content = (
      <div className="space-y-2">
        <Scoreline match={payload.match} compact={compact} />
        {payload.points?.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-bold tracking-widest text-slate-400 uppercase">Auswertung</p>
            <div className="flex flex-wrap gap-1.5">
              {payload.points.map((p: any) => (
                <span
                  key={p.user_id}
                  className={clsx(
                    "rounded-md px-1.5 py-0.5 text-[11px] font-semibold",
                    p.exact_correct ? "bg-gold/20 text-gold" : p.winner_correct ? "bg-emerald-500/15 text-emerald-200" : "bg-white/5 text-slate-400",
                  )}
                >
                  {p.display_name} {p.icon} +{p.points}
                </span>
              ))}
            </div>
          </div>
        )}
        {payload.leaderboard?.length > 0 && !compact && (
          <div>
            <p className="mb-1 text-[10px] font-bold tracking-widest text-slate-400 uppercase">Neue Rangliste</p>
            <ol className="space-y-0.5 text-xs">
              {payload.leaderboard.map((r: any) => (
                <li key={r.user_id} className="flex justify-between gap-2 text-slate-300">
                  <span>
                    <span className="inline-block w-5 font-bold text-slate-500">{r.rank}</span>
                    {r.display_name}
                  </span>
                  <span className="font-semibold text-white tabular-nums">{r.points}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    );
  } else if ((type === "NEXT_ROUND" || type === "MATCHUP") && payload.matches) {
    content = (
      <div className="space-y-1.5">
        <p className="text-xs font-semibold text-slate-300">{(payload.rounds ?? []).join(", ")}</p>
        {payload.matches.map((m: any) => (
          <div key={m.id}>
            <Scoreline match={m} compact />
            <p className="mt-0.5 text-right text-[10px] text-slate-500">{kickoffShort(m.kickoff_at)}</p>
          </div>
        ))}
      </div>
    );
  } else if ((type === "KICKOFF" || type === "HALFTIME") && payload.match) {
    const match = type === "HALFTIME" ? { ...payload.match, home_score: payload.home_score, away_score: payload.away_score } : payload.match;
    content = (
      <div className="space-y-1.5">
        <Scoreline match={match} compact={compact} />
        {type === "KICKOFF" && (
          <p className="flex items-center gap-1 text-xs text-slate-400">
            <Lock className="size-3" /> Tipps für dieses Spiel sind gesperrt.
          </p>
        )}
      </div>
    );
  } else if (type === "CHAMPION" && payload.champion) {
    content = (
      <div className="flex items-center gap-3 rounded-xl bg-gradient-to-r from-gold/20 to-transparent p-3">
        <TeamLogo team={payload.champion} size={compact ? 40 : 56} glow className="animate-glow" />
        <div>
          <p className="display text-lg font-bold text-gold">{payload.champion.name}</p>
          <p className="flex items-center gap-1 text-xs text-slate-200">
            <Trophy className="size-3.5 text-gold" /> Tippspiel-Sieger: <strong>{payload.winner?.display_name}</strong> ({payload.winner?.points} P.)
          </p>
        </div>
      </div>
    );
  } else if (type === "OPEN_PICKS" && payload.match) {
    content = (
      <div className="space-y-1.5">
        <Scoreline match={payload.match} compact />
        <p className="text-xs text-orange-200">Noch nicht getippt: {(payload.users ?? []).join(", ")}</p>
      </div>
    );
  } else {
    content = <p className="text-sm whitespace-pre-line text-slate-200">{lines.slice(1).join("\n") || message.body}</p>;
  }

  return (
    <div className="rounded-2xl bg-gradient-to-r from-afc/60 via-gold/50 to-nfc/60 p-px shadow-[0_10px_30px_-15px_rgb(245_196_81/0.35)]" data-testid={`bot-${type}`}>
      <div className="rounded-[15px] bg-ink-900/95 p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className={clsx("rounded px-1.5 py-0.5 text-[10px] font-black tracking-widest uppercase", meta.tone)}>{meta.label}</span>
          {(type === "FINAL" || type === "CORRECTION") && payload.match?.round_label && (
            <span className="truncate text-[11px] text-slate-400">{payload.match.round_label}</span>
          )}
        </div>
        {content}
      </div>
    </div>
  );
}
