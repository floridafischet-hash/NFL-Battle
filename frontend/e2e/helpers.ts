import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const ADMIN = {
  username: process.env.E2E_ADMIN_USER ?? "admin",
  password: process.env.E2E_ADMIN_PASSWORD ?? "",
};

export const FIELD = {
  AFC: ["KC", "BUF", "BAL", "HOU", "MIA", "LAC", "PIT"],
  NFC: ["PHI", "DET", "SF", "TB", "MIN", "GB", "LAR"],
} as const;

export async function loginUI(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/");
  await expect(page.getByRole("button", { name: "Benutzermenü" })).toBeVisible();
}

export async function apiLogin(request: APIRequestContext, username: string, password: string): Promise<string> {
  const r = await request.post("/api/auth/login", { data: { username, password } });
  expect(r.status(), await r.text()).toBe(200);
  return (await r.json()).access_token;
}

export async function call<T = any>(
  request: APIRequestContext,
  token: string,
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  url: string,
  data?: unknown,
  expected?: number,
): Promise<{ status: number; body: T }> {
  const r = await request.fetch(url, { method, data, headers: { Authorization: `Bearer ${token}` } });
  const text = await r.text();
  if (expected !== undefined) expect(r.status(), `${method} ${url}: ${text}`).toBe(expected);
  return { status: r.status(), body: text ? JSON.parse(text) : undefined };
}

export function isoOffset(minutes: number): string {
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

export const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:8090";
export const MOCK_URL = process.env.E2E_MOCK_URL ?? "http://localhost:8091";

/** Browser storage state of a logged-in user – reuses an existing token instead of logging in again
 * (nginx allows only a handful of logins per minute and IP). */
export function tokenState(token: string) {
  return { cookies: [], origins: [{ origin: new URL(BASE_URL).origin, localStorage: [{ name: "nbb.token", value: token }] }] };
}

/** Tell the OpenAI mock (scripts/openai_mock.py) the real scores, keyed by the home team. */
export async function mockResults(request: APIRequestContext, results: Record<string, [number, number]>) {
  const r = await request.post(`${MOCK_URL}/__mock/results`, { data: results });
  expect(r.status()).toBe(200);
}
