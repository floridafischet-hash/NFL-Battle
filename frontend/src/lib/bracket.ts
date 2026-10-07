import type { BracketSlot, Conference, SeasonMatch, Team } from "./types";

export const FEEDERS: Record<string, string[]> = {
  "AFC-DIV-1": ["AFC-WC-1", "AFC-WC-2", "AFC-WC-3"],
  "AFC-DIV-2": ["AFC-WC-1", "AFC-WC-2", "AFC-WC-3"],
  "AFC-CONF": ["AFC-DIV-1", "AFC-DIV-2"],
  "NFC-DIV-1": ["NFC-WC-1", "NFC-WC-2", "NFC-WC-3"],
  "NFC-DIV-2": ["NFC-WC-1", "NFC-WC-2", "NFC-WC-3"],
  "NFC-CONF": ["NFC-DIV-1", "NFC-DIV-2"],
  SB: ["AFC-CONF", "NFC-CONF"],
};

/** Visual fallback lines while a pairing is still unknown (classic bracket look). */
export const PLACEHOLDER_ORIGINS: Record<string, [string, string]> = {
  "AFC-DIV-1": ["BYE:AFC", "AFC-WC-1"],
  "AFC-DIV-2": ["AFC-WC-2", "AFC-WC-3"],
  "AFC-CONF": ["AFC-DIV-1", "AFC-DIV-2"],
  "NFC-DIV-1": ["BYE:NFC", "NFC-WC-1"],
  "NFC-DIV-2": ["NFC-WC-2", "NFC-WC-3"],
  "NFC-CONF": ["NFC-DIV-1", "NFC-DIV-2"],
  SB: ["AFC-CONF", "NFC-CONF"],
};

export const COLUMNS: { key: string; conference: Conference | null; title: string; slots: string[] }[] = [
  { key: "afc-wc", conference: "AFC", title: "Wild Card", slots: ["AFC-WC-1", "AFC-WC-2", "AFC-WC-3"] },
  { key: "afc-div", conference: "AFC", title: "Divisional", slots: ["AFC-DIV-1", "AFC-DIV-2"] },
  { key: "afc-conf", conference: "AFC", title: "Conference", slots: ["AFC-CONF"] },
  { key: "sb", conference: null, title: "Super Bowl", slots: ["SB"] },
  { key: "nfc-conf", conference: "NFC", title: "Conference", slots: ["NFC-CONF"] },
  { key: "nfc-div", conference: "NFC", title: "Divisional", slots: ["NFC-DIV-1", "NFC-DIV-2"] },
  { key: "nfc-wc", conference: "NFC", title: "Wild Card", slots: ["NFC-WC-1", "NFC-WC-2", "NFC-WC-3"] },
];

export const ROUND_TITLES: Record<string, string> = {
  WILD_CARD: "Wild Card",
  DIVISIONAL: "Divisional Round",
  CONFERENCE: "Conference Championship",
  SUPER_BOWL: "Super Bowl",
};

export function slotLabel(slot: string): string {
  if (slot === "SB") return "Super Bowl";
  const [conf, kind, n] = slot.split("-");
  if (kind === "CONF") return `${conf} Championship`;
  if (kind === "DIV") return `${conf} Divisional ${n}`;
  return `${conf} Wild Card ${n}`;
}

export function originOf(team: Team | null, slot: string, bySlot: Map<string, BracketSlot>, byes: Partial<Record<Conference, Team>>): string | null {
  if (!team) return null;
  const conf = slot.slice(0, 3) as Conference;
  if (slot.includes("-DIV-") && byes[conf]?.id === team.id) return `BYE:${conf}`;
  for (const feeder of FEEDERS[slot] ?? []) {
    const f = bySlot.get(feeder);
    if (f && (f.home?.id === team.id || f.away?.id === team.id)) return feeder;
  }
  return null;
}

/** Build bracket slots from the official match list (live mode: actual pairings + my picks). */
export function slotsFromMatches(matches: SeasonMatch[]): BracketSlot[] {
  const slots: BracketSlot[] = matches.map((m) => {
    const pickValid = m.my_pick != null && [m.home_team?.id, m.away_team?.id].includes(m.my_pick.winner_team_id);
    return {
      slot: m.slot,
      match_id: m.id,
      round: m.round,
      round_label: m.round_label,
      conference: m.conference,
      home: m.home_team,
      away: m.away_team,
      teams_source: m.home_team && m.away_team ? "actual" : m.home_team || m.away_team ? "partial" : "none",
      home_origin: null,
      away_origin: null,
      status: m.status,
      locked: m.locked,
      kickoff_at: m.kickoff_at,
      lock_at: m.lock_at,
      venue: m.venue,
      home_score: m.home_score,
      away_score: m.away_score,
      winner_team_id: m.winner_team_id,
      has_pick: m.my_pick != null,
      pick_hidden: false,
      pick: m.my_pick,
      pick_state: m.my_pick ? (pickValid ? "valid" : "invalid") : "none",
      effective_winner_team_id: m.winner_team_id,
      points: m.my_points,
      winner_correct: m.my_points != null ? m.my_pick?.winner_team_id === m.winner_team_id : null,
      exact_correct: null,
      pending_change_request: null,
    };
  });
  return slots;
}

export function withOrigins(slots: BracketSlot[], byes: Partial<Record<Conference, Team>>): BracketSlot[] {
  const bySlot = new Map(slots.map((s) => [s.slot, s]));
  return slots.map((s) => ({
    ...s,
    home_origin: s.home_origin ?? originOf(s.home, s.slot, bySlot, byes),
    away_origin: s.away_origin ?? originOf(s.away, s.slot, bySlot, byes),
  }));
}

export function isLive(slot: Pick<BracketSlot, "status" | "locked" | "kickoff_at">, now = Date.now()): boolean {
  return slot.status === "LOCKED" && !!slot.kickoff_at && new Date(slot.kickoff_at).getTime() <= now;
}
