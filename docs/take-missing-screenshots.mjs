/**
 * Capture evidence.png and resolution.png using Playwright route mocking.
 * No API key required — we intercept /api/chat and /api/accuse.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, 'screenshots');
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } });
const page = await ctx.newPage();

// ── Mock /api/chat — return scripted SSE with evidence clues ──────────────────
await page.route('**/api/chat', async route => {
  const tokens = [
    'I was in the kitchen all evening, I assure you. ',
    'The dinner service ran until half past ten, ',
    'and I retired to my quarters at 11 PM sharp. ',
    'I never set foot in the east wing that night. ',
    'The wine decanter — yes, I decanted the port before dinner as always, ',
    'but that was at seven o\'clock, in the dining room. ',
    'Lord Ashworth always drank alone after midnight. ',
    'I have the household ledger if you need proof of the kitchen inventory.'
  ];

  const metadata = {
    consistency_passed: true,
    new_clues: [
      { clue_id: 'c001', suspect_id: 'butler', text: '11 PM',           category: 'time',     turn: 1 },
      { clue_id: 'c002', suspect_id: 'butler', text: 'kitchen',         category: 'location', turn: 1 },
      { clue_id: 'c003', suspect_id: 'butler', text: 'east wing',       category: 'location', turn: 1 },
      { clue_id: 'c004', suspect_id: 'butler', text: 'decanter',        category: 'object',   turn: 1 },
      { clue_id: 'c005', suspect_id: 'butler', text: 'ledger',          category: 'object',   turn: 1 },
      { clue_id: 'c006', suspect_id: 'butler', text: 'half past ten',   category: 'time',     turn: 1 },
    ],
    pressure_delta: 1,
    new_pressure_level: 2,
    new_evidence_found: true,
  };

  // Build SSE body
  let body = tokens.map(t => `data: ${JSON.stringify({ type: 'token', content: t })}\n\n`).join('');
  body += `data: ${JSON.stringify({ type: 'done', metadata })}\n\n`;

  await route.fulfill({
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
    },
    body,
  });
});

// ── Mock /api/accuse — return a correct verdict with narrative ────────────────
await page.route('**/api/accuse', async route => {
  await route.fulfill({
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      is_correct: true,
      correct_culprit_id: 'butler',
      correct_motive: 'Beckett had embezzled household funds for years and feared exposure.',
      correct_method: 'Arsenic dissolved in the decanted port wine.',
      score: 78,
      resolution_narrative:
        'The room fell silent as you produced the household ledger — the very one ' +
        'Beckett had mentioned so casually. The figures did not lie: thousands of pounds ' +
        'diverted over seven years, concealed beneath false invoices and phantom suppliers.\n\n' +
        'Lord Ashworth had found the discrepancy that very afternoon. He had called Beckett ' +
        'to the study and given him an ultimatum: confess by morning, or face the constable. ' +
        'Beckett smiled thinly, agreed, and returned to the kitchen to decant the evening port.\n\n' +
        'The arsenic was kept in the scullery, labelled as rat poison. A measured dose — ' +
        'enough to stop a heart by midnight, not enough to be obvious to a country doctor ' +
        'called in haste. Beckett had counted on exactly that. He had not counted on you.\n\n' +
        '"I wondered," Beckett said quietly, "how long it would take." He did not resist ' +
        'as the constable led him from the manor. Outside, the first light of dawn broke ' +
        'over Ashworth\'s grounds — and for the first time in seven years, the accounts were clean.',
    }),
  });
});

// ── Navigate and start game ───────────────────────────────────────────────────
await page.goto('http://localhost:3000');
await page.waitForLoadState('networkidle');
await page.getByRole('button', { name: /begin investigation/i }).click();
await page.waitForURL('**/game/**', { timeout: 10000 });
await page.waitForLoadState('networkidle');

// ── Select butler, send a question ───────────────────────────────────────────
await page.locator('nav button').first().click();
await page.waitForTimeout(500);

await page.locator('textarea').fill('Where were you between 9 and 11 PM, and did you have access to the wine decanter?');
await page.keyboard.press('Enter');

// Wait for the mock response to stream and evidence to appear
await page.waitForTimeout(3000);

// ── Expand evidence locker (click the › chevron on the right panel) ──────────
// The EvidenceLocker has a header div that acts as a toggle
const rightAside = page.locator('aside').last();
const header = rightAside.locator('div').first();
await header.click().catch(() => {});
await page.waitForTimeout(600);

// ── Evidence screenshot ───────────────────────────────────────────────────────
await page.screenshot({ path: join(OUT, 'evidence.png') });
console.log('✓ evidence.png');

// ── Make accusation ───────────────────────────────────────────────────────────
await page.getByRole('button', { name: /make accusation/i }).click();
await page.waitForTimeout(400);

await page.locator('select').selectOption({ index: 0 });
// Motive and Method are <input type="text">, not textareas
await page.getByPlaceholder('Why did they do it?').fill('Beckett embezzled household funds for seven years. Lord Ashworth confronted him after discovering forged invoices in the ledger.');
await page.getByPlaceholder('How was it done?').fill('Arsenic dissolved in the decanted port wine before dinner — a ritual only Beckett performed, giving him sole opportunity.');
await page.waitForTimeout(300);

// Submit
await page.locator('button').filter({ hasText: /make accusation/i }).last().click();

// Wait for resolution narrative to appear
await page.waitForFunction(
  () => document.body.innerText.includes('fell silent') || document.body.innerText.includes('score') || document.body.innerText.includes('78'),
  { timeout: 15000 }
).catch(() => {});
await page.waitForTimeout(1500);

// ── Resolution screenshot ─────────────────────────────────────────────────────
await page.screenshot({ path: join(OUT, 'resolution.png') });
console.log('✓ resolution.png');

await browser.close();
console.log('\nDone — both screenshots saved to docs/screenshots/');
