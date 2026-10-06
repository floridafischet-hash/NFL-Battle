"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { put } from "@/lib/api";
import { useBracket } from "@/lib/queries";
import { useToast } from "@/lib/toast";
import type { BracketSlot, BracketView, Season, Team } from "@/lib/types";

import { BracketBoard } from "./BracketBoard";
import { ScoreTipDialog, type ScoreTip } from "./ScoreTipDialog";

export function useBracketMutations(seasonId: number) {
  const qc = useQueryClient();
  const toast = useToast();
  const [pendingSlot, setPendingSlot] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: ({ slot, tip }: { slot: string; tip: ScoreTip }) =>
      put<BracketView>(`/api/seasons/${seasonId}/bracket/me/picks/${slot}`, tip),
    onMutate: ({ slot }) => setPendingSlot(slot),
    onSuccess: (data) => {
      qc.setQueryData(["bracket", seasonId, "me"], data);
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["matches", seasonId] });
    },
    onError: (err) => toast.error("Tipp nicht gespeichert", err instanceof Error ? err.message : undefined),
    onSettled: () => setPendingSlot(null),
  });
  return { mutation, pendingSlot };
}

/** The interactive bracket of the signed-in user. */
export function BracketEditor({ season, size = "large" }: { season: Season; size?: "large" | "compact" }) {
  const router = useRouter();
  const bracket = useBracket(season.id, "me");
  const { mutation, pendingSlot } = useBracketMutations(season.id);
  const [scoreSlot, setScoreSlot] = useState<BracketSlot | null>(null);
  const editable = season.status !== "COMPLETED";

  if (!bracket.data) return null;
  const view = bracket.data;

  const pick = (slot: BracketSlot, team: Team) => {
    if (slot.pick?.winner_team_id === team.id && slot.pick_state === "valid") {
      if (season.score_tips_enabled) setScoreSlot(slot);
      return;
    }
    // a new winner invalidates an earlier score tip
    mutation.mutate({ slot: slot.slot, tip: { winner_team_id: team.id, winner_score: null, loser_score: null } });
  };

  return (
    <>
      <BracketBoard
        slots={view.slots}
        byes={view.byes}
        mode={editable ? "edit" : "view"}
        size={size}
        seasonYear={season.year}
        scoreTips={season.score_tips_enabled}
        championTeamId={season.champion_team?.id ?? view.champion_team_id}
        championLabel={season.champion_team ? "Champion" : "Dein Champion"}
        pendingSlot={pendingSlot}
        onPick={pick}
        onScore={(slot) => setScoreSlot(slot)}
        onOpen={(slot) => router.push(`/spiele/${slot.match_id}`)}
      />
      <ScoreTipDialog
        slot={scoreSlot}
        busy={mutation.isPending}
        onClose={() => setScoreSlot(null)}
        onSave={(tip) => {
          if (!scoreSlot) return;
          mutation.mutate({ slot: scoreSlot.slot, tip }, { onSuccess: () => setScoreSlot(null) });
        }}
      />
    </>
  );
}
