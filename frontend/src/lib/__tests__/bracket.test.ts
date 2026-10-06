import { describe, expect, it } from "vitest";

import { slotLabel, slotsFromMatches, withOrigins } from "../bracket";
import type { SeasonMatch, Team } from "../types";

const team = (id: number, abbr: string, seed: number): Team => ({
  id,
  name: abbr,
  short_name: abbr,
  abbreviation: abbr,
  city: null,
  conference: "AFC",
  division: null,
  logo_url: null,
  primary_color: "#000000",
  secondary_color: "#ffffff",
  is_active: true,
  seed,
});

const KC = team(1, "KC", 1);
const BUF = team(2, "BUF", 2);
const PIT = team(7, "PIT", 7);

function match(slot: string, home: Team | null, away: Team | null, extra: Partial<SeasonMatch> = {}): SeasonMatch {
  return {
    id: slot.length,
    season_id: 1,
    slot,
    round: slot.includes("WC") ? "WILD_CARD" : "DIVISIONAL",
    round_label: "",
    conference: "AFC",
    home_team: home,
    away_team: away,
    kickoff_at: null,
    lock_at: null,
    venue: null,
    status: "OPEN",
    locked: false,
    home_score: null,
    away_score: null,
    winner_team_id: null,
    result_source: null,
    finalized_at: null,
    my_pick: null,
    my_points: null,
    distribution: null,
    ...extra,
  };
}

describe("bracket helpers", () => {
  it("labels slots in German", () => {
    expect(slotLabel("AFC-WC-2")).toBe("AFC Wild Card 2");
    expect(slotLabel("NFC-CONF")).toBe("NFC Championship");
    expect(slotLabel("SB")).toBe("Super Bowl");
  });

  it("derives connector origins incl. the bye", () => {
    const slots = withOrigins(
      slotsFromMatches([
        match("AFC-WC-1", BUF, PIT, { status: "FINAL", winner_team_id: BUF.id }),
        match("AFC-DIV-1", KC, BUF),
      ]),
      { AFC: KC },
    );
    const div = slots.find((s) => s.slot === "AFC-DIV-1")!;
    expect(div.home_origin).toBe("BYE:AFC");
    expect(div.away_origin).toBe("AFC-WC-1");
  });

  it("marks my pick invalid when the team is not in the pairing", () => {
    const [slot] = slotsFromMatches([match("AFC-WC-1", BUF, PIT, { my_pick: { winner_team_id: KC.id, winner_score: null, loser_score: null } })]);
    expect(slot.pick_state).toBe("invalid");
  });
});
