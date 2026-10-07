"use client";

import { useEffect, useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { Button, Modal } from "@/components/ui";
import { slotLabel } from "@/lib/bracket";
import type { BracketSlot, Team, Tip } from "@/lib/types";

export interface ScoreTip {
  winner_team_id: number;
  winner_score: number | null;
  loser_score: number | null;
}

function initial(team: Team | null, pick: Tip | null): string {
  if (!team || !pick || pick.winner_score == null) return "";
  return String(team.id === pick.winner_team_id ? pick.winner_score : pick.loser_score);
}

export function ScoreTipDialog({
  slot,
  onClose,
  onSave,
  busy,
}: {
  slot: BracketSlot | null;
  onClose: () => void;
  onSave: (tip: ScoreTip) => void;
  busy?: boolean;
}) {
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slot) return;
    setHome(initial(slot.home, slot.pick));
    setAway(initial(slot.away, slot.pick));
    setError(null);
  }, [slot]);

  if (!slot || !slot.home || !slot.away) return null;
  const homeTeam = slot.home;
  const awayTeam = slot.away;

  const save = () => {
    const h = Number(home);
    const a = Number(away);
    if (home === "" || away === "" || !Number.isInteger(h) || !Number.isInteger(a) || h < 0 || a < 0 || h > 99 || a > 99) {
      setError("Bitte zwei ganze Zahlen zwischen 0 und 99 eingeben.");
      return;
    }
    if (h === a) {
      setError("Playoff-Spiele enden nicht unentschieden.");
      return;
    }
    const homeWins = h > a;
    onSave({
      winner_team_id: homeWins ? homeTeam.id : awayTeam.id,
      winner_score: Math.max(h, a),
      loser_score: Math.min(h, a),
    });
  };

  const row = (team: Team, value: string, set: (v: string) => void, label: string) => (
    <label className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.03] p-3">
      <TeamLogo team={team} size={44} />
      <span className="min-w-0 flex-1">
        <span className="block text-[11px] tracking-wider text-slate-400 uppercase">{label}</span>
        <span className="block truncate font-semibold text-white">{team.name}</span>
      </span>
      <input
        type="number"
        inputMode="numeric"
        min={0}
        max={99}
        value={value}
        onChange={(e) => set(e.target.value)}
        className="focus-ring display h-14 w-20 rounded-xl border border-white/10 bg-ink-900 text-center text-3xl font-bold text-white"
        aria-label={`Punkte ${team.short_name}`}
      />
    </label>
  );

  return (
    <Modal open onClose={onClose} title={`Ergebnis tippen · ${slotLabel(slot.slot)}`}>
      <div className="space-y-3">
        {row(homeTeam, home, setHome, "Heim")}
        {row(awayTeam, away, setAway, "Gast")}
        <p className="text-xs text-slate-400">
          Der Sieger deines Tipps richtet sich nach dem Ergebnis. Ein exakter Endstand bringt Bonuspunkte.
        </p>
        {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</p>}
        <div className="flex flex-wrap justify-end gap-2 pt-2">
          {slot.pick?.winner_score != null && (
            <Button
              variant="ghost"
              onClick={() => slot.pick && onSave({ winner_team_id: slot.pick.winner_team_id, winner_score: null, loser_score: null })}
              disabled={busy}
            >
              Ergebnis entfernen
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Abbrechen
          </Button>
          <Button variant="primary" onClick={save} loading={busy} data-testid="score-save">
            Speichern
          </Button>
        </div>
      </div>
    </Modal>
  );
}
