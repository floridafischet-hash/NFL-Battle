"use client";

import clsx from "clsx";
import { Check, Clock3, Loader2, Lock, Pencil, TriangleAlert, X } from "lucide-react";
import type { CSSProperties } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { isLive } from "@/lib/bracket";
import { kickoffShort } from "@/lib/format";
import type { BracketSlot, Conference, Team } from "@/lib/types";

export type BoardMode = "edit" | "view" | "live";
export type BoardSize = "compact" | "large";
type Register = (key: string) => (el: HTMLElement | null) => void;

export const CONF_COLOR: Record<Conference | "SB", string> = { AFC: "#ef3349", NFC: "#2f7bff", SB: "#f5c451" };

export interface CardProps {
  slot: BracketSlot;
  size: BoardSize;
  mode: BoardMode;
  register: Register;
  onPick?: (slot: BracketSlot, team: Team) => void;
  onScore?: (slot: BracketSlot) => void;
  onOpen?: (slot: BracketSlot) => void;
  pending?: boolean;
  highlight?: "same" | "different" | "hidden" | "missing" | null;
  allTeams: Map<number, Team>;
  scoreTips: boolean;
}

function scoreFor(slot: BracketSlot, team: Team | null): number | null {
  if (!team || slot.status !== "FINAL") return null;
  return team.id === slot.home?.id ? slot.home_score : slot.away_score;
}

function PickBadge({ state }: { state: "pick" | "hit" | "miss" }) {
  return (
    <span
      className={clsx(
        "flex size-5 shrink-0 items-center justify-center rounded-full",
        state === "pick" && "bg-gold text-ink-950 shadow-[0_0_10px_rgb(245_196_81/0.7)]",
        state === "hit" && "bg-emerald-400 text-ink-950 shadow-[0_0_10px_rgb(52_211_153/0.7)]",
        state === "miss" && "bg-red-500 text-white",
      )}
      title={state === "pick" ? "Dein Tipp" : state === "hit" ? "Richtig getippt" : "Falsch getippt"}
    >
      {state === "miss" ? <X className="size-3.5" strokeWidth={3} /> : <Check className="size-3.5" strokeWidth={3} />}
    </span>
  );
}

function TeamRow({
  slot,
  team,
  side,
  size,
  register,
  clickable,
  onClick,
  conf,
}: {
  slot: BracketSlot;
  team: Team | null;
  side: "home" | "away";
  size: BoardSize;
  register: Register;
  clickable: boolean;
  onClick?: () => void;
  conf: string;
}) {
  const final = slot.status === "FINAL";
  const isWinner = final && team != null && slot.winner_team_id === team.id;
  const isLoser = final && team != null && slot.winner_team_id !== team.id;
  const picked = team != null && slot.pick?.winner_team_id === team.id && slot.pick_state !== "hidden";
  const advancing = !final && team != null && slot.effective_winner_team_id === team.id;
  const score = scoreFor(slot, team);
  const rowH = size === "large" ? "h-11" : "h-9";
  const logo = size === "large" ? 30 : 24;
  const style: CSSProperties | undefined =
    team && (isWinner || advancing)
      ? { background: `linear-gradient(90deg, ${team.primary_color}55, ${team.primary_color}10 70%, transparent)` }
      : undefined;

  const content = (
    <>
      <span
        className={clsx("absolute inset-y-1 left-0 w-[3px] rounded-r-full transition", isWinner || advancing ? "opacity-100" : "opacity-0")}
        style={{ background: conf, boxShadow: `0 0 10px ${conf}` }}
      />
      {team ? (
        <span key={team.id} className="flex min-w-0 flex-1 animate-pop-in items-center gap-1.5" title={team.name}>
          <TeamLogo team={team} size={logo} glow={isWinner} />
          {team.seed != null && <span className="w-3 text-center text-[10px] font-bold text-slate-500 tabular-nums">{team.seed}</span>}
          <span
            className={clsx(
              "truncate font-semibold",
              size === "large" ? "text-[14px]" : "text-[12.5px]",
              isLoser ? "text-slate-500" : "text-slate-100",
              isWinner && "text-white",
            )}
          >
            {team.short_name}
          </span>
        </span>
      ) : (
        <span className="flex min-w-0 flex-1 items-center gap-2 text-slate-600">
          <TeamLogo team={null} size={logo} className="opacity-40" />
          <span className={clsx("font-semibold tracking-wider", size === "large" ? "text-[13px]" : "text-[11.5px]")}>TBD</span>
        </span>
      )}
      {score != null && (
        <span className={clsx("display ml-1 tabular-nums", size === "large" ? "text-lg" : "text-base", isWinner ? "text-white" : "text-slate-500")}>
          {score}
        </span>
      )}
      {picked && (
        <span className="ml-1">
          <PickBadge state={final ? (slot.winner_team_id === team?.id ? "hit" : "miss") : "pick"} />
        </span>
      )}
    </>
  );

  const className = clsx(
    "relative flex w-full items-center gap-1 overflow-hidden px-2 text-left transition",
    rowH,
    isLoser && "opacity-60",
    clickable && "cursor-pointer hover:bg-white/[0.07] focus-ring",
    picked && !final && "ring-1 ring-gold/50 ring-inset",
  );

  if (clickable && team) {
    return (
      <button
        type="button"
        ref={register(`${slot.slot}:${side}`)}
        onClick={onClick}
        className={className}
        style={style}
        aria-pressed={picked}
        aria-label={`${team.name} als Sieger tippen`}
        data-testid={`pick-${slot.slot}-${team.abbreviation}`}
      >
        {content}
      </button>
    );
  }
  return (
    <div ref={register(`${slot.slot}:${side}`)} className={className} style={style}>
      {content}
    </div>
  );
}

export function MatchCard({ slot, size, mode, register, onPick, onScore, onOpen, pending, highlight, allTeams, scoreTips }: CardProps) {
  const conf = CONF_COLOR[slot.conference ?? "SB"];
  const canPick = mode === "edit" && !slot.locked && slot.home != null && slot.away != null;
  const live = isLive(slot);
  const pickTeam = slot.pick ? allTeams.get(slot.pick.winner_team_id) : undefined;
  const width = size === "large" ? "w-[184px]" : "w-[158px]";

  let status: React.ReactNode;
  if (slot.status === "FINAL") status = <span className="font-bold text-slate-300">FINAL</span>;
  else if (slot.status === "VOID") status = <span className="font-bold text-amber-300">ANNULLIERT</span>;
  else if (live)
    status = (
      <span className="flex items-center gap-1 font-bold text-red-400">
        <span className="size-1.5 animate-pulse rounded-full bg-red-500" /> LIVE
      </span>
    );
  else if (slot.locked) status = <span className="flex items-center gap-1 text-slate-400"><Lock className="size-3" /> Gesperrt</span>;
  else status = <span className="text-slate-400">{kickoffShort(slot.kickoff_at)}</span>;

  return (
    <div
      ref={register(slot.slot)}
      data-slot={slot.slot}
      className={clsx(
        "group relative rounded-xl border bg-ink-850/90 shadow-[0_10px_30px_-18px_rgb(0_0_0/0.9)] backdrop-blur transition duration-200",
        width,
        canPick ? "border-white/12 hover:-translate-y-0.5 hover:border-white/25" : "border-white/8",
        highlight === "different" && "ring-2 ring-amber-400/80",
        highlight === "same" && "ring-1 ring-emerald-400/50",
        onOpen && "cursor-pointer hover:border-white/20",
      )}
      style={canPick ? { boxShadow: `0 0 0 1px ${conf}22, 0 12px 30px -18px ${conf}` } : undefined}
      onClick={onOpen && !canPick ? () => onOpen(slot) : undefined}
    >
      <div className="overflow-hidden rounded-t-xl">
        <TeamRow slot={slot} team={slot.home} side="home" size={size} register={register} clickable={canPick} onClick={() => slot.home && onPick?.(slot, slot.home)} conf={conf} />
        <div className="h-px bg-white/6" />
        <TeamRow slot={slot} team={slot.away} side="away" size={size} register={register} clickable={canPick} onClick={() => slot.away && onPick?.(slot, slot.away)} conf={conf} />
      </div>
      <div className={clsx("flex items-center justify-between gap-1 border-t border-white/6 px-2", size === "large" ? "h-7 text-[11px]" : "h-6 text-[10px]")}>
        {status}
        <span className="flex items-center gap-1">
          {slot.pick_state === "hidden" && (
            <span className="flex items-center gap-1 text-slate-500" title="Erst nach Tipp-Lock sichtbar">
              <Lock className="size-3" /> verdeckt
            </span>
          )}
          {slot.pick_state === "pending" && pickTeam && (
            <span className="flex items-center gap-1 text-slate-400" title={`Dein Tipp ${pickTeam.name} – Gegner steht noch nicht fest`}>
              <Clock3 className="size-3" /> {pickTeam.abbreviation}
            </span>
          )}
          {slot.pick_state === "invalid" && pickTeam && (
            <span className="flex items-center gap-1 text-amber-300" title={`Getippt: ${pickTeam.name} – nicht in dieser Partie`}>
              <TriangleAlert className="size-3" /> {pickTeam.abbreviation} raus
            </span>
          )}
          {scoreTips && slot.pick && slot.pick_state === "valid" && slot.pick.winner_score != null && slot.status !== "FINAL" && (
            <span className="text-slate-400 tabular-nums">
              {slot.pick.winner_score}:{slot.pick.loser_score}
            </span>
          )}
          {slot.points != null && (
            <span
              className={clsx(
                "rounded px-1 font-bold tabular-nums",
                slot.exact_correct ? "bg-gold/20 text-gold" : slot.points > 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-white/5 text-slate-500",
              )}
            >
              +{slot.points}
              {slot.exact_correct ? " 🎯" : ""}
            </span>
          )}
          {canPick && scoreTips && slot.pick_state === "valid" && onScore && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onScore(slot);
              }}
              className="focus-ring -mr-1 flex size-6 items-center justify-center rounded-md text-slate-400 hover:bg-white/10 hover:text-gold"
              aria-label="Ergebnis tippen"
              title="Ergebnis tippen"
              data-testid={`score-${slot.slot}`}
            >
              <Pencil className="size-3.5" />
            </button>
          )}
        </span>
      </div>
      {pending && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-ink-950/50">
          <Loader2 className="size-5 animate-spin text-gold" />
        </div>
      )}
    </div>
  );
}

export function ByeCard({ team, size, register, conference }: { team: Team | undefined; size: BoardSize; register: Register; conference: Conference }) {
  const width = size === "large" ? "w-[184px]" : "w-[158px]";
  return (
    <div ref={register(`BYE:${conference}`)} className={clsx("rounded-xl border border-dashed border-white/12 bg-ink-850/60", width)}>
      <div className={clsx("flex items-center gap-2 px-2", size === "large" ? "h-11" : "h-9")}>
        <TeamLogo team={team ?? null} size={size === "large" ? 30 : 24} />
        <span className="w-3 text-center text-[10px] font-bold text-slate-500">1</span>
        <span className={clsx("truncate font-semibold text-slate-200", size === "large" ? "text-[14px]" : "text-[12.5px]")}>
          {team?.short_name ?? "Seed 1"}
        </span>
        <span className="ml-auto rounded bg-white/8 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-slate-400">BYE</span>
      </div>
    </div>
  );
}
