/**
 * Capture README screenshots using Playwright.
 * Run: node docs/take-screenshots.mjs
 * Requires: frontend on :3000, backend on :8000
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, 'screenshots');
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx    = await browser.newContext({ viewport: { width: 1400, height: 860 } });
const page   = await ctx.newPage();

async function shot(name) {
  await page.waitForTimeout(800);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false });
  console.log(`✓ ${name}.png`);
}

/* ── Home — Case File tab ── */
await page.goto('http://localhost:3000');
await page.waitForLoadState('networkidle');
await shot('home');

/* ── History tab ── */
await page.getByRole('button', { name: /history/i }).click();
await page.waitForTimeout(600);
await shot('history');

/* ── Start a game ── */
await page.getByRole('button', { name: /case file/i }).click();
await page.getByRole('button', { name: /begin investigation/i }).click();
await page.waitForURL('**/game/**', { timeout: 10000 });
await page.waitForLoadState('networkidle');
await shot('game');

/* ── Case file sidebar close-up (left panel) ── */
const sidebar = page.locator('aside').first();
await sidebar.screenshot({ path: join(OUT, 'case-file.png') });
console.log('✓ case-file.png');

/* ── Click first suspect ── */
await page.locator('nav button').first().click();
await page.waitForTimeout(500);
await shot('chat');

/* ── Accusation modal ── */
await page.getByRole('button', { name: /make accusation/i }).click();
await page.waitForTimeout(500);
await shot('accusation');

await browser.close();
console.log('\nAll screenshots saved to docs/screenshots/');
