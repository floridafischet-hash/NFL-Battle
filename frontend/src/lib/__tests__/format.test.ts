import { describe, expect, it } from "vitest";

import { countdown, roman, superBowlName } from "../format";

describe("format", () => {
  it("names the Super Bowl of a season", () => {
    expect(superBowlName(2026)).toBe("Super Bowl LXI");
    expect(superBowlName(2024)).toBe("Super Bowl LIX");
    expect(roman(1994)).toBe("MCMXCIV");
  });

  it("counts down to kickoff", () => {
    const now = Date.UTC(2027, 0, 1, 12, 0, 0);
    const c = countdown(new Date(now + ((26 * 60 + 5) * 60 + 7) * 1000).toISOString(), now);
    expect(c).toEqual({ days: 1, hours: 2, minutes: 5, seconds: 7, done: false });
    expect(countdown(new Date(now - 1000).toISOString(), now).done).toBe(true);
    expect(countdown(null, now).done).toBe(true);
  });
});
