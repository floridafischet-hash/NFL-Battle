"use client";

import clsx from "clsx";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { COLUMNS, PLACEHOLDER_ORIGINS } from "@/lib/bracket";
import { superBowlName } from "@/lib/format";
import type { BracketSlot, Conference, Team } from "@/lib/types";

import { ByeCard, CONF_COLOR, MatchCard, type BoardMode, type BoardSize } from "./MatchCard";

interface PathSpec {
  key: string;
  d: string;
  color: string;
  kind: "won" | "predicted" | "placeholder";
}

export interface BracketBoardProps {
  slots: BracketSlot[];
  byes: Partial<Record<Conference, Team>>;
  mode: BoardMode;
  size?: BoardSize;
  seasonYear?: number;
  scoreTips?: boolean;
  championTeamId?: number | null;
  championLabel?: string;
  pendingSlot?: string | null;
  highlights?: Record<string, "same" | "different" | "hidden" | "missing">;
  onPick?: (slot: BracketSlot, team: Team) => void;
  onScore?: (slot: BracketSlot) => void;
  onOpen?: (slot: BracketSlot) => void;
  /** Scale the board down to the available width (down to MIN_SCALE, then scroll). */
  fit?: boolean;
}

const MIN_SCALE = 0.74;

function elbow(x1: number, y1: number, x2: number, y2: number): string {
  if (Math.abs(y1 - y2) < 1) return `M${x1},${y1} H${x2}`;
  const xm = (x1 + x2) / 2;
  const dir = Math.sign(x2 - x1) || 1;
  const vdir = Math.sign(y2 - y1);
  const r = Math.min(10, Math.abs(y2 - y1) / 2, Math.abs(xm - x1));
  return [
    `M${x1},${y1}`,
    `H${xm - dir * r}`,
    `Q${xm},${y1} ${xm},${y1 + vdir * r}`,
    `V${y2 - vdir * r}`,
    `Q${xm},${y2} ${xm + dir * r},${y2}`,
    `H${x2}`,
  ].join(" ");
}

function Trophy({ size = 34 }: { size?: number }) {
  return (
    <svg viewBox="0 0 40 64" width={size * 0.62} height={size} aria-hidden className="animate-glow">
      <defs>
        <linearGradient id="tr-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff6d6" />
          <stop offset="0.45" stopColor="#e7e9ee" />
          <stop offset="1" stopColor="#9aa3b2" />
        </linearGradient>
      </defs>
      <ellipse cx="22" cy="11" rx="9.5" ry="6" transform="rotate(-30 22 11)" fill="url(#tr-g)" />
      <path d="M17 18 C17 30 15 40 13 50 H27 C25 40 23 30 23 18 Z" fill="url(#tr-g)" />
      <rect x="9" y="50" width="22" height="6" rx="1.5" fill="#cfd5df" />
      <rect x="7" y="56" width="26" height="6" rx="1.5" fill="#f5c451" />
    </svg>
  );
}

export function BracketBoard({
  slots,
  byes,
  mode,
  size = "large",
  seasonYear,
  scoreTips = false,
  championTeamId,
  championLabel,
  pendingSlot,
  highlights,
  onPick,
  onScore,
  onOpen,
  fit = false,
}: BracketBoardProps) {
  const boardRef = useRef<HTMLDivElement>(null);
  const nodes = useRef(new Map<string, HTMLElement>());
  const [paths, setPaths] = useState<PathSpec[]>([]);
  const [box, setBox] = useState({ w: 0, h: 0 });

  const bySlot = useMemo(() => new Map(slots.map((s) => [s.slot, s])), [slots]);
  const allTeams = useMemo(() => {
    const map = new Map<number, Team>();
    for (const s of slots) for (const t of [s.home, s.away]) if (t) map.set(t.id, t);
    for (const t of Object.values(byes)) if (t) map.set(t.id, t);
    return map;
  }, [slots, byes]);

  const register = useCallback(
    (key: string) => (el: HTMLElement | null) => {
      if (el) nodes.current.set(key, el);
      else nodes.current.delete(key);
    },
    [],
  );

  const measure = useCallback(() => {
    const board = boardRef.current;
    if (!board) return;
    const base = board.getBoundingClientRect();
    // the board may be scaled (fit mode): convert screen pixels back to board pixels
    const k = base.width ? board.offsetWidth / base.width : 1;
    const rect = (key: string) => {
      const el = nodes.current.get(key);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        left: (r.left - base.left) * k,
        right: (r.right - base.left) * k,
        cy: ((r.top + r.bottom) / 2 - base.top) * k,
      };
    };
    const out: PathSpec[] = [];
    for (const [slotKey, placeholders] of Object.entries(PLACEHOLDER_ORIGINS)) {
      const s = bySlot.get(slotKey);
      if (!s) continue;
      (["home", "away"] as const).forEach((side, idx) => {
        const target = rect(`${slotKey}:${side}`);
        if (!target) return;
        const team = s[side];
        const origin = side === "home" ? s.home_origin : s.away_origin;
        const known = team != null && origin != null;
        let srcKey = known ? origin! : placeholders[idx];
        if (known && !origin!.startsWith("BYE")) {
          const o = bySlot.get(origin!);
          if (o?.home?.id === team!.id) srcKey = `${origin}:home`;
          else if (o?.away?.id === team!.id) srcKey = `${origin}:away`;
        }
        const src = rect(srcKey) ?? rect(placeholders[idx]);
        if (!src) return;
        const leftToRight = src.right <= target.left + 2;
        const x1 = leftToRight ? src.right : src.left;
        const x2 = leftToRight ? target.left : target.right;
        let kind: PathSpec["kind"] = "placeholder";
        if (known) {
          const o = origin!.startsWith("BYE") ? null : bySlot.get(origin!);
          kind = !o || o.status === "FINAL" ? "won" : "predicted";
        }
        const conf: Conference | "SB" = slotKey === "SB" ? (side === "home" ? "AFC" : "NFC") : (s.conference ?? "SB");
        out.push({ key: `${slotKey}:${side}`, d: elbow(x1, src.cy, x2, target.cy), color: CONF_COLOR[conf], kind });
      });
    }
    setPaths(out);
    setBox({ w: board.scrollWidth, h: board.scrollHeight });
  }, [bySlot]);

  useLayoutEffect(() => {
    measure();
  }, [measure, slots]);

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(board);
    document.fonts?.ready.then(() => measure()).catch(() => undefined);
    return () => ro.disconnect();
  }, [measure]);

  const outerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const outer = outerRef.current;
    const board = boardRef.current;
    if (!fit || !outer || !board) return;
    const update = () => {
      const w = board.offsetWidth;
      const h = board.offsetHeight;
      setNatural({ w, h });
      setScale(w ? Math.max(MIN_SCALE, Math.min(1, outer.clientWidth / w)) : 1);
    };
    const ro = new ResizeObserver(update);
    ro.observe(outer);
    ro.observe(board);
    return () => ro.disconnect();
  }, [fit]);
  const scaled = fit && scale < 1;

  const champion = championTeamId != null ? allTeams.get(championTeamId) : undefined;
  const sb = bySlot.get("SB");
  const bodyH = size === "large" ? 540 : 420;
  const gap = size === "large" ? "gap-x-7" : "gap-x-[14px]";

  return (
    <div ref={outerRef} className="scrollbar-thin -mx-1 overflow-x-auto px-1 pb-2">
      <div
        className="mx-auto"
        style={scaled ? { width: natural.w * scale, height: natural.h * scale } : undefined}
      >
      <div
        ref={boardRef}
        className={clsx("relative mx-auto flex w-max items-stretch", gap)}
        style={scaled ? { transform: `scale(${scale})`, transformOrigin: "top left" } : undefined}
        data-testid="bracket-board"
      >
        <svg className="pointer-events-none absolute top-0 left-0 z-0 overflow-visible" width={box.w} height={box.h} aria-hidden>
          {paths.map((p) => (
            <path
              key={`${p.key}-${p.kind}-${p.d.length}`}
              d={p.d}
              fill="none"
              stroke={p.kind === "placeholder" ? "rgb(255 255 255 / 0.10)" : p.color}
              strokeWidth={p.kind === "won" ? 2.2 : p.kind === "predicted" ? 1.8 : 1.4}
              strokeOpacity={p.kind === "predicted" ? 0.75 : 1}
              strokeDasharray={p.kind === "predicted" ? "6 6" : p.kind === "won" ? 1 : undefined}
              pathLength={p.kind === "won" ? 1 : undefined}
              strokeLinecap="round"
              style={
                p.kind === "won"
                  ? { filter: `drop-shadow(0 0 4px ${p.color})`, strokeDashoffset: 0, animation: "draw-line 700ms ease-out both", ["--len" as string]: 1 }
                  : p.kind === "predicted"
                    ? { animation: "dash-flow 1.2s linear infinite", filter: `drop-shadow(0 0 3px ${p.color}88)` }
                    : undefined
              }
            />
          ))}
        </svg>

        {COLUMNS.map((col) => {
          const isSb = col.key === "sb";
          const tone = col.conference === "AFC" ? "text-afc-soft" : col.conference === "NFC" ? "text-nfc-soft" : "text-gold";
          return (
            <div key={col.key} className="relative z-10 flex flex-col">
              <div className="mb-3 flex h-8 flex-col items-center justify-end text-center">
                {col.conference && (
                  <span className={clsx("text-[10px] font-bold tracking-[0.25em]", tone)}>{col.conference}</span>
                )}
                <span className="display text-[12px] font-semibold tracking-[0.12em] text-slate-300">{isSb ? "Finale" : col.title}</span>
              </div>
              <div className="flex flex-col justify-around" style={{ height: bodyH }}>
                {col.key.endsWith("-wc") && col.conference && (
                  <ByeCard team={byes[col.conference]} size={size} register={register} conference={col.conference} />
                )}
                {!isSb &&
                  col.slots.map((key) => {
                    const s = bySlot.get(key);
                    if (!s) return null;
                    return (
                      <MatchCard
                        key={key}
                        slot={s}
                        size={size}
                        mode={mode}
                        register={register}
                        onPick={onPick}
                        onScore={onScore}
                        onOpen={onOpen}
                        pending={pendingSlot === key}
                        highlight={highlights?.[key] ?? null}
                        allTeams={allTeams}
                        scoreTips={scoreTips}
                      />
                    );
                  })}
                {isSb && sb && (
                  <div className="flex flex-col items-center gap-4">
                    <div className="flex flex-col items-center">
                      <Trophy size={size === "large" ? 56 : 44} />
                      <p className="display mt-1 text-center text-[13px] font-bold tracking-[0.18em] text-gradient-gold sm:text-sm">
                        {seasonYear ? superBowlName(seasonYear) : "Super Bowl"}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-gradient-to-b from-gold/70 via-gold/20 to-gold/60 p-px shadow-[0_0_40px_-6px_rgb(245_196_81/0.55)]">
                      <MatchCard
                        slot={sb}
                        size={size}
                        mode={mode}
                        register={register}
                        onPick={onPick}
                        onScore={onScore}
                        onOpen={onOpen}
                        pending={pendingSlot === "SB"}
                        highlight={highlights?.SB ?? null}
                        allTeams={allTeams}
                        scoreTips={scoreTips}
                      />
                    </div>
                    <div className="flex flex-col items-center text-center" data-testid="champion">
                      <div className="relative flex items-center justify-center">
                        <div className="absolute size-24 rounded-full bg-gold/15 blur-2xl" />
                        {champion ? (
                          <div key={champion.id} className="animate-pop-in">
                            <TeamLogo team={champion} size={size === "large" ? 84 : 64} glow className="animate-glow" />
                          </div>
                        ) : (
                          <div className={clsx("flex items-center justify-center rounded-full border-2 border-dashed border-gold/30 text-gold/40", size === "large" ? "size-20" : "size-16")}>
                            ?
                          </div>
                        )}
                      </div>
                      <p className="display mt-2 text-[10px] font-bold tracking-[0.35em] text-gold">{championLabel ?? "Champion"}</p>
                      <p className="display text-lg font-bold text-white">{champion?.short_name ?? "Noch offen"}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
}
