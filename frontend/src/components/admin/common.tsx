"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { get } from "@/lib/api";
import type { Season, Team } from "@/lib/types";

export interface AdminMatch {
  id: number;
  season_id: number;
  slot: string;
  round: string;
  round_label: string;
  conference: "AFC" | "NFC" | null;
  home_team: Team | null;
  away_team: Team | null;
  kickoff_at: string | null;
  lock_at: string | null;
  venue: string | null;
  status: "OPEN" | "LOCKED" | "FINAL" | "VOID";
  locked: boolean;
  home_score: number | null;
  away_score: number | null;
  winner_team_id: number | null;
  result_source: string | null;
  review_required: number;
  picks: number;
  result_check_requested_at: string | null;
}

export function useAdminSeasons() {
  return useQuery({ queryKey: ["seasons"], queryFn: () => get<Season[]>("/api/seasons") });
}

export function useAdminMatches(seasonId: number | null) {
  return useQuery({
    queryKey: ["admin-matches", seasonId],
    queryFn: () => get<AdminMatch[]>(`/api/admin/seasons/${seasonId}/matches`),
    enabled: seasonId != null,
  });
}

export function useSeasonTeams(seasonId: number | null) {
  return useQuery({
    queryKey: ["season-teams", seasonId],
    queryFn: () => get<Team[]>(`/api/seasons/${seasonId}/teams`),
    enabled: seasonId != null,
  });
}

export function useInvalidateAdmin() {
  const qc = useQueryClient();
  return () => {
    for (const key of ["admin-matches", "season-teams", "seasons", "dashboard", "matches", "bracket", "leaderboard", "admin-summary", "admin-change-requests", "agent-overview", "audit"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
  };
}

/** ISO (UTC) -> value for <input type="datetime-local"> in the browser's timezone. */
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

export function errorText(e: unknown): string | undefined {
  return e instanceof Error ? e.message : undefined;
}
