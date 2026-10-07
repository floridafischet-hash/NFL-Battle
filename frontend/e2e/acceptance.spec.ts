/**
 * Final acceptance test (section 39 of the requirements) – a complete season on a fresh install:
 * admin creates season, teams & pairings → users log in and tip → tips lock → OpenClaw reports
 * results → points, leaderboard, NFL Bot, next round → bracket comparison → Super Bowl →
 * overall winner → Hall of Fame.
 */
import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

import { ADMIN, FIELD, apiLogin, call, isoOffset, loginUI } from "./helpers";

const SEASON = { name: "2030/2031", year: 2030 };
const USERS = {
  anna: { username: "anna", display: "Anna", password: "anna-pass-123" },
  ben: { username: "ben", display: "Ben", password: "ben-pass-123" },
};

// actual results (home : away) per round
const RESULTS: Record<string, [number, number]>[] = [
  { "AFC-WC-1": [27, 17], "AFC-WC-2": [28, 14], "AFC-WC-3": [24, 20], "NFC-WC-1": [31, 23], "NFC-WC-2": [20, 23], "NFC-WC-3": [17, 24] },
  { "AFC-DIV-1": [30, 21], "AFC-DIV-2": [24, 27], "NFC-DIV-1": [20, 27], "NFC-DIV-2": [35, 24] },
  { "AFC-CONF": [24, 20], "NFC-CONF": [17, 27] },
  { SB: [31, 24] },
];

// Anna tips via the UI (order matters: a slot becomes pickable once its pairing is known)
const ANNA_PICKS: [string, string][] = [
  ["AFC-WC-1", "BUF"], ["AFC-WC-2", "BAL"], ["AFC-WC-3", "HOU"],
  ["NFC-WC-1", "DET"], ["NFC-WC-2", "SF"], ["NFC-WC-3", "TB"],
  ["AFC-DIV-1", "KC"], ["AFC-DIV-2", "BUF"], ["NFC-DIV-1", "PHI"], ["NFC-DIV-2", "DET"],
  ["AFC-CONF", "KC"], ["NFC-CONF", "PHI"], ["SB", "KC"],
];
const BEN_PICKS: [string, string][] = [
  ["AFC-WC-1", "PIT"], ["AFC-WC-2", "BAL"], ["AFC-WC-3", "HOU"],
  ["NFC-WC-1", "DET"], ["NFC-WC-2", "GB"], ["NFC-WC-3", "TB"],
  ["AFC-DIV-1", "KC"], ["AFC-DIV-2", "BAL"], ["NFC-DIV-1", "GB"], ["NFC-DIV-2", "DET"],
  ["AFC-CONF", "BAL"], ["NFC-CONF", "DET"], ["SB", "DET"],
];

interface Ctx {
  adminToken: string;
  annaToken: string;
  benToken: string;
  agentToken: string;
  seasonId: number;
  teams: Record<string, number>;
}
const ctx = {} as Ctx;

async function adminMatches(request: APIRequestContext) {
  const { body } = await call<any[]>(request, ctx.adminToken, "GET", `/api/admin/seasons/${ctx.seasonId}/matches`, undefined, 200);
  return Object.fromEntries(body.map((m) => [m.slot, m]));
}

async function asUser(browser: Browser, username: string, password: string): Promise<Page> {
  const context = await browser.newContext({ locale: "de-DE", timezoneId: "Europe/Berlin", viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  await loginUI(page, username, password);
  return page;
}

test.describe.serial("Abnahme: komplette Saison", () => {
  test.beforeAll(async ({ request }) => {
    expect(ADMIN.password, "E2E_ADMIN_PASSWORD must be set").not.toBe("");
    ctx.adminToken = await apiLogin(request, ADMIN.username, ADMIN.password);
    const { body } = await call<any[]>(request, ctx.adminToken, "GET", "/api/teams", undefined, 200);
    ctx.teams = Object.fromEntries(body.map((t) => [t.abbreviation, t.id]));
  });

  test("1. Admin legt Benutzer an", async ({ page }) => {
    await loginUI(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin?tab=users");
    for (const u of Object.values(USERS)) {
      await page.getByRole("button", { name: "Benutzer anlegen" }).click();
      await page.getByLabel("Benutzername (Login)").fill(u.username);
      await page.getByLabel("Anzeigename").fill(u.display);
      await page.getByLabel("Passwort (min. 6 Zeichen)").fill(u.password);
      await page.getByRole("dialog").getByRole("button", { name: "Anlegen", exact: true }).click();
      await expect(page.getByText(`@${u.username}`)).toBeVisible();
    }
  });

  test("2. Admin erstellt die Saison", async ({ page, request }) => {
    await loginUI(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin?tab=seasons");
    await page.getByLabel("Name (z. B. 2026/2027)").fill(SEASON.name);
    await page.getByLabel("Startjahr").fill(String(SEASON.year));
    await page.getByRole("button", { name: "Saison erstellen" }).click();
    await expect(page.getByText(`Saison ${SEASON.name}`)).toBeVisible();
    const { body } = await call<any[]>(request, ctx.adminToken, "GET", "/api/seasons", undefined, 200);
    ctx.seasonId = body.find((s) => s.name === SEASON.name).id;
  });

  test("3. Admin setzt die Teams per Drag & Drop und erzeugt die Paarungen", async ({ page, request }) => {
    await loginUI(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin?tab=setup");
    // real drag & drop of the #1 seed (filter the team list first, like a user would)
    await page.getByLabel("Team suchen").fill("Chiefs");
    const chip = page.getByTestId("team-chip-KC");
    const target = page.getByTestId("seed:AFC:1");
    const from = (await chip.boundingBox())!;
    const to = (await target.boundingBox())!;
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.mouse.move(from.x + from.width / 2 + 20, from.y + from.height / 2 + 10, { steps: 5 });
    await page.mouse.move(to.x + to.width / 2, to.y + 20, { steps: 15 });
    await page.mouse.up();
    await expect(target.locator("select")).toHaveValue(String(ctx.teams.KC));
    await page.getByLabel("Team suchen").fill("");
    // remaining seeds via the dropdown alternative
    const { body: teams } = await call<any[]>(request, ctx.adminToken, "GET", "/api/teams", undefined, 200);
    const nameOf = (abbr: string) => teams.find((t) => t.abbreviation === abbr).name;
    for (const conf of ["AFC", "NFC"] as const) {
      for (const [i, abbr] of FIELD[conf].entries()) {
        if (conf === "AFC" && i === 0) continue;
        await page.getByTestId(`seed:${conf}:${i + 1}`).locator("select").selectOption({ label: nameOf(abbr) });
      }
    }
    await page.getByRole("button", { name: "Speichern" }).first().click();
    await expect(page.getByText("Setzliste gespeichert")).toBeVisible();
    await page.getByRole("button", { name: "Wild Card erzeugen" }).click();
    await expect(page.getByText("Wild-Card-Paarungen erzeugt")).toBeVisible();
    await expect(page.getByTestId(`match:${(await adminMatches(request))["AFC-WC-1"].id}:home`)).toContainText("Bills");
  });

  test("4. Admin aktiviert die Saison und setzt die Kickoff-Zeiten", async ({ page, request }) => {
    await loginUI(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin?tab=seasons");
    await page.getByRole("button", { name: "Aktivieren" }).click();
    await expect(page.getByText("Saison aktiviert")).toBeVisible();
    const matches = await adminMatches(request);
    for (const slot of Object.keys(RESULTS[0])) {
      await call(request, ctx.adminToken, "PATCH", `/api/admin/matches/${matches[slot].id}`, { kickoff_at: isoOffset(24 * 60), venue: "Stadion" }, 200);
    }
  });

  test("5. Benutzer meldet sich an und baut sein Bracket per Klick", async ({ browser, request }) => {
    const page = await asUser(browser, USERS.anna.username, USERS.anna.password);
    ctx.annaToken = await apiLogin(request, USERS.anna.username, USERS.anna.password);
    await page.goto("/bracket");
    for (const [slot, abbr] of ANNA_PICKS) {
      const button = page.getByTestId(`pick-${slot}-${abbr}`);
      await button.click();
      await expect(button).toHaveAttribute("aria-pressed", "true");
    }
    await expect(page.getByTestId("champion")).toContainText("Chiefs");
    // score tip for the first game: Bills 27:17
    await page.getByTestId("score-AFC-WC-1").click();
    await page.getByLabel("Punkte Bills").fill("27");
    await page.getByLabel("Punkte Steelers").fill("17");
    await page.getByTestId("score-save").click();
    await expect(page.locator('[data-slot="AFC-WC-1"]')).toContainText("27:17");
    await page.getByTestId("submit-bracket").click();
    await expect(page.getByText(/Abgegeben/).first()).toBeVisible();
    await page.context().close();
  });

  test("6. Zweiter Benutzer tippt und chattet live", async ({ browser, request }) => {
    ctx.benToken = await apiLogin(request, USERS.ben.username, USERS.ben.password);
    for (const [slot, abbr] of BEN_PICKS) {
      await call(request, ctx.benToken, "PUT", `/api/seasons/${ctx.seasonId}/bracket/me/picks/${slot}`, { winner_team_id: ctx.teams[abbr] }, 200);
    }
    // realtime chat: Anna sees Ben's message without reloading
    const anna = await asUser(browser, USERS.anna.username, USERS.anna.password);
    await anna.goto("/chat");
    await expect(anna.getByText("Live verbunden")).toBeVisible();
    const ben = await asUser(browser, USERS.ben.username, USERS.ben.password);
    await ben.goto("/chat");
    await ben.getByTestId("chat-input").fill("Packers machen das Ding! 🧀");
    await ben.getByTestId("chat-send").click();
    await expect(anna.getByText("Packers machen das Ding! 🧀")).toBeVisible();
    await anna.context().close();
    await ben.context().close();
  });

  test("7. Fremde Tipps sind vor dem Lock verdeckt", async ({ browser }) => {
    const page = await asUser(browser, USERS.anna.username, USERS.anna.password);
    await page.goto("/brackets");
    await page.getByRole("link", { name: /Ben/ }).click();
    await expect(page.getByText(/Tipps sind noch verdeckt/)).toBeVisible();
    await expect(page.locator('[data-slot="AFC-WC-1"]')).toContainText("verdeckt");
    await page.context().close();
  });

  test("8. Tipps werden zum Kickoff gesperrt", async ({ request }) => {
    const matches = await adminMatches(request);
    for (const slot of Object.keys(RESULTS[0])) {
      await call(request, ctx.adminToken, "PATCH", `/api/admin/matches/${matches[slot].id}`, { kickoff_at: isoOffset(-180) }, 200);
    }
    const r = await call(request, ctx.annaToken, "PUT", `/api/seasons/${ctx.seasonId}/bracket/me/picks/AFC-WC-1`, { winner_team_id: ctx.teams.PIT });
    expect(r.status).toBe(409);
    // after the lock the friend's picks are visible
    const { body } = await call<any>(request, ctx.annaToken, "GET", `/api/seasons/${ctx.seasonId}/bracket/${(await call<any>(request, ctx.benToken, "GET", "/api/me")).body.id}`, undefined, 200);
    expect(body.slots.find((s: any) => s.slot === "AFC-WC-1").pick.winner_team_id).toBe(ctx.teams.PIT);
  });

  test("9. Admin erzeugt den OpenClaw-Token", async ({ page }) => {
    await loginUI(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin?tab=agent");
    await page.getByRole("button", { name: "Token erstellen" }).click();
    const token = (await page.getByTestId("agent-token").textContent())!.trim();
    expect(token).toMatch(/^nbb_/);
    ctx.agentToken = token;
  });

  async function report(request: APIRequestContext, match: any, home: number, away: number, extra: object = {}) {
    return call<any>(request, ctx.agentToken, "POST", "/api/agent/results", {
      match_id: match.id,
      home_team: match.home_team.abbreviation,
      away_team: match.away_team.abbreviation,
      home_score: home,
      away_score: away,
      winner: home > away ? match.home_team.abbreviation : match.away_team.abbreviation,
      source: "ESPN",
      source_url: `https://www.espn.com/nfl/game/_/gameId/${match.id}`,
      timestamp: new Date().toISOString(),
      ...extra,
    });
  }

  test("10. OpenClaw meldet Ergebnisse, das Backend validiert", async ({ request }) => {
    const matches = await adminMatches(request);
    // agent token cannot use user endpoints, plausibility is checked
    expect((await call(request, ctx.agentToken, "GET", "/api/me")).status).toBe(403);
    const wrongTeams = await report(request, matches["AFC-WC-1"], 27, 17, { home_team: "NE" });
    expect(wrongTeams.status).toBe(422);
    const tie = await report(request, matches["AFC-WC-1"], 20, 20);
    expect(tie.status).toBe(422);
    const pending = await call<any[]>(request, ctx.agentToken, "GET", "/api/agent/matches/pending", undefined, 200);
    expect(pending.body.map((m) => m.slot)).toEqual(expect.arrayContaining(Object.keys(RESULTS[0])));
    for (const [slot, [h, a]] of Object.entries(RESULTS[0])) {
      const r = await report(request, matches[slot], h, a);
      expect(r.status, JSON.stringify(r.body)).toBe(200);
      expect(r.body.status).toBe("APPLIED");
    }
    const dup = await report(request, matches["AFC-WC-1"], 27, 17);
    expect(dup.body.status).toBe("DUPLICATE");
  });

  test("11. Punkte, Rangliste, NFL Bot und nächste Runde", async ({ browser }) => {
    const page = await asUser(browser, USERS.anna.username, USERS.anna.password);
    await page.goto("/rangliste");
    const annaRow = page.getByRole("row", { name: /Anna/ });
    await expect(annaRow.locator("td").nth(2)).toHaveText("6"); // 3 (exact 27:17) + 3 correct winners
    await page.goto("/chat");
    await expect(page.getByTestId("bot-FINAL").first()).toBeVisible();
    await expect(page.getByTestId("bot-NEXT_ROUND").first()).toBeVisible();
    await page.goto("/bracket");
    const div1 = page.locator('[data-slot="AFC-DIV-1"]');
    await expect(div1).toContainText("Chiefs");
    await expect(div1).toContainText("Texans");
    await page.context().close();
  });

  test("12. Bracket-Vergleich mit einem Freund", async ({ browser }) => {
    const page = await asUser(browser, USERS.anna.username, USERS.anna.password);
    await page.goto("/brackets");
    await page.getByLabel("Spieler B").selectOption({ label: "Ben" });
    await page.getByRole("button", { name: "Vergleichen" }).click();
    await expect(page.getByRole("heading", { name: "Bracket-Vergleich" })).toBeVisible();
    await expect(page.getByText("unterschiedlich")).toBeVisible();
    await expect(page.getByRole("row", { name: /AFC Wild Card 1/ })).toContainText("Steelers");
    await page.context().close();
  });

  test("13. Restliche Runden bis zum Super Bowl", async ({ request }) => {
    // living bracket: before the next lock users fix picks of eliminated teams
    const fixes: [string, string, string][] = [
      ["anna", "NFC-CONF", "DET"],
    ];
    for (let round = 1; round < RESULTS.length; round++) {
      const matches = await adminMatches(request);
      for (const [user, slot, abbr] of fixes.filter(([, s]) => Object.keys(RESULTS[round]).includes(s))) {
        const token = user === "anna" ? ctx.annaToken : ctx.benToken;
        await call(request, token, "PUT", `/api/seasons/${ctx.seasonId}/bracket/me/picks/${slot}`, { winner_team_id: ctx.teams[abbr] }, 200);
      }
      if (round === 3) {
        await call(request, ctx.benToken, "PUT", `/api/seasons/${ctx.seasonId}/bracket/me/picks/SB`, { winner_team_id: ctx.teams.GB }, 200);
      }
      for (const [slot, [h, a]] of Object.entries(RESULTS[round])) {
        expect(matches[slot].home_team, `${slot} pairing created automatically`).not.toBeNull();
        await call(request, ctx.adminToken, "PATCH", `/api/admin/matches/${matches[slot].id}`, { kickoff_at: isoOffset(-180) }, 200);
        const r = await report(request, matches[slot], h, a);
        expect(r.body.status, JSON.stringify(r.body)).toBe("APPLIED");
      }
    }
    const { body } = await call<any[]>(request, ctx.annaToken, "GET", `/api/seasons/${ctx.seasonId}/leaderboard`, undefined, 200);
    const points = Object.fromEntries(body.map((r) => [r.user.display_name, r.points]));
    expect(points).toEqual({ Anna: 13, Ben: 8 });
  });

  test("14. Gesamtsieger wird angezeigt und die Hall of Fame aktualisiert", async ({ browser }) => {
    const page = await asUser(browser, USERS.anna.username, USERS.anna.password);
    await page.goto("/chat");
    await expect(page.getByTestId("bot-CHAMPION")).toContainText("Anna");
    await page.goto("/hall-of-fame");
    await expect(page.getByText(`SAISON ${SEASON.name}`)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Hall of Fame" })).toBeVisible();
    await expect(page.getByText("Tippspiel-Sieger").first()).toBeVisible();
    await expect(page.getByText("13 Punkte").first()).toBeVisible();
    await page.goto("/rangliste");
    await expect(page.getByText(`Saison ${SEASON.name} · abgeschlossen`)).toBeVisible();
    await page.goto("/");
    await expect(page.getByTestId("champion")).toContainText("Chiefs");
    await page.context().close();
  });
});
