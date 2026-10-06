"use client";

import { useQuery } from "@tanstack/react-query";

import { get } from "./api";
import type {
  BracketOverviewEntry,
  BracketView,
  ChatMessage,
  DashboardData,
  HallOfFameData,
  LeaderboardRow,
  MatchDetail,
  NotificationItem,
  Season,
  SeasonMatch,
  Team,
  UserRef,
  UserStats,
} from "./types";

export function useSeasons() {
  return useQuery({ queryKey: ["seasons"], queryFn: () => get<Season[]>("/api/seasons"), staleTime: 60_000 });
}

export function useCurrentSeason() {
  return useQuery({
    queryKey: ["seasons", "current"],
    queryFn: () => get<Season | null>("/api/seasons/current"),
    staleTime: 60_000,
  });
}

/** The season shown on a page: explicit selection or the current one. */
export function useSelectedSeason(selected: number | null) {
  const current = useCurrentSeason();
  const seasons = useSeasons();
  const id = selected ?? current.data?.id ?? null;
  const season = seasons.data?.find((s) => s.id === id) ?? current.data ?? null;
  return { id, season, seasons: seasons.data ?? [], isLoading: current.isLoading || seasons.isLoading };
}

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => get<DashboardData>("/api/dashboard") });
}

export function useBracket(seasonId: number | null, userId: string = "me") {
  return useQuery({
    queryKey: ["bracket", seasonId, userId],
    queryFn: () => get<BracketView>(`/api/seasons/${seasonId}/bracket/${userId}`),
    enabled: seasonId != null,
  });
}

export function useSeasonMatches(seasonId: number | null) {
  return useQuery({
    queryKey: ["matches", seasonId],
    queryFn: () => get<SeasonMatch[]>(`/api/seasons/${seasonId}/matches`),
    enabled: seasonId != null,
  });
}

export function useMatch(matchId: number) {
  return useQuery({ queryKey: ["match", matchId], queryFn: () => get<MatchDetail>(`/api/matches/${matchId}`) });
}

export function useLeaderboard(seasonId: number | null) {
  return useQuery({
    queryKey: ["leaderboard", seasonId],
    queryFn: () => get<LeaderboardRow[]>(`/api/seasons/${seasonId}/leaderboard`),
    enabled: seasonId != null,
  });
}

export function useBracketsOverview(seasonId: number | null) {
  return useQuery({
    queryKey: ["brackets", seasonId],
    queryFn: () => get<BracketOverviewEntry[]>(`/api/seasons/${seasonId}/brackets`),
    enabled: seasonId != null,
  });
}

export function useChat() {
  return useQuery({
    queryKey: ["chat"],
    queryFn: () => get<ChatMessage[]>("/api/chat/messages?limit=60"),
    staleTime: Infinity,
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => get<{ unread: number; items: NotificationItem[] }>("/api/notifications"),
    staleTime: 30_000,
  });
}

export function usePlayers() {
  return useQuery({ queryKey: ["users"], queryFn: () => get<UserRef[]>("/api/users"), staleTime: 60_000 });
}

export function useTeams() {
  return useQuery({ queryKey: ["teams"], queryFn: () => get<Team[]>("/api/teams"), staleTime: 300_000 });
}

export function useUserStats(userId: string, seasonId: number | null) {
  return useQuery({
    queryKey: ["stats", "user", userId, seasonId],
    queryFn: () => get<UserStats>(`/api/stats/users/${userId}${seasonId ? `?season_id=${seasonId}` : ""}`),
  });
}

export function useHallOfFame() {
  return useQuery({ queryKey: ["hall-of-fame"], queryFn: () => get<HallOfFameData>("/api/hall-of-fame") });
}

export function useOnline() {
  return useQuery({ queryKey: ["online"], queryFn: () => get<UserRef[]>("/api/chat/online"), staleTime: 15_000 });
}
