import { expect, test } from "@playwright/test";

import { ADMIN, loginUI } from "./helpers";

test("Smartphone: Menü, Dashboard und horizontal scrollbares Bracket", async ({ page }) => {
  await loginUI(page, ADMIN.username, ADMIN.password);
  // navigation lives in a mobile drawer
  await page.getByRole("button", { name: "Menü öffnen" }).click();
  await page.getByRole("navigation").getByRole("link", { name: "Mein Bracket", exact: true }).click();
  await page.waitForURL("**/bracket");
  await expect(page.getByRole("heading", { name: "Mein Bracket", exact: true })).toBeVisible();
  const board = page.getByTestId("bracket-board");
  await expect(board).toBeVisible();
  const scroller = board.locator("xpath=ancestor::div[contains(@class,'overflow-x-auto')][1]");
  const { scrollWidth, clientWidth } = await scroller.evaluate((el) => ({ scrollWidth: el.scrollWidth, clientWidth: el.clientWidth }));
  expect(scrollWidth).toBeGreaterThan(clientWidth);
  // no horizontal scrolling of the whole page
  const pageOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(pageOverflow).toBeLessThanOrEqual(1);
  // touch targets: team rows are at least 36px high
  const row = page.locator('[data-slot="AFC-WC-1"] button, [data-slot="AFC-WC-1"] > div > div').first();
  const box = await row.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(36);
});
