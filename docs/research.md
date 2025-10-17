## ArabSeed Download Flow Recon (High Potential)

### Scope
- Target: Series page → Episode download → 720p quality via ArabSeed server only
- Goal: Reach a stable, automatable path to the final direct media URL (.mp4 or .m3u8)

### Base URLs and Entry Points
- Site base used by live redirects: `https://a.asd.homes/main0/`
- Example episode download page visited: `.../مسلسل-high-potential-.../download/`

### Search UI and Results Structure
- Search entrypoint/page:
  - Search input textbox name: "إبحث عن عمل او ممثل ...." (role=textbox)
  - Submits to: `https://a.asd.homes/find/?word=<QUERY>&type=`

- Result items:
  - Card/link selector: `a.movie__block`
  - Title inside card: `.movie__title`
  - Type badge (when present): `.mv__pro__type` or `.mv__type` (may indicate Movie/Series)
  - Series queries like "High Potential" often return individual episode links (each `a.movie__block` points to a specific episode page).
  - Movie queries like "Bad man" usually return a single movie detail link.

- Playwright examples:
```ts
// Perform search from home
await page.goto('https://a.asd.homes/main0/');
await page.getByRole('textbox', { name: 'إبحث عن عمل او ممثل' }).fill('High Potential');
await page.getByRole('textbox', { name: 'إبحث عن عمل او ممثل' }).press('Enter');

// Extract results
const results = await page.evaluate(() =>
  Array.from(document.querySelectorAll('a.movie__block')).map(card => ({
    href: (card as HTMLAnchorElement).href,
    title: card.querySelector('.movie__title')?.textContent?.trim() || null,
    badge: card.querySelector('.mv__pro__type')?.textContent?.trim()
        || card.querySelector('.mv__type')?.textContent?.trim() || null,
  }))
);

// Heuristic classification per result
for (const r of results) {
  // If badge contains keywords, use that; otherwise fallback to link structure heuristics
  r['kind'] = /مسلسل|Series|TV/i.test(r.badge || '') ? 'series'
            : /فيلم|Movie/i.test(r.badge || '') ? 'movie'
            : /\/مسلسل-|%D9%85%D8%B3%D9%84%D8%B3%D9%84-/.test(r.href) ? 'series'
            : /\/فيلم-|%D9%81%D9%8A%D9%84%D9%85-/.test(r.href) ? 'movie'
            : 'unknown';
}
```

### Key Arabic UI Texts
- "سيرفرات التحميل" (download servers)
- Qualities: "تحميل بجودة 720p", "تحميل بجودة 480p"
- Server to choose: "سيرفر عرب سيد المباشر"
- Action buttons: "التحميل الان", "اضغط للتحميل", "تحميل"

### Selectors (robust suggestions)
- 720p accordion header: text contains "تحميل بجودة 720p"
- 720p server list items under the expanded section; use the item name text when possible:
  - ArabSeed direct server: role=link with name contains "سيرفر عرب سيد المباشر"
- Primary action buttons:
  - First step: role=button name="التحميل الان" or role=link name="التحميل الان"
  - Intermediate/final: role=button name="اضغط للتحميل"
  - Final direct link: role=link name="تحميل" (often adjacent to file name/size)

### Flow Variants Observed
- Variant A (multi-step, with two 15s timers):
  1) Click 720p → click "سيرفر عرب سيد المباشر".
  2) Land on intermediate page with 15s timer. After countdown, a new button appears.
  3) First click opens an ad in a new tab. Close the ad tab, return to original tab.
  4) Click the button again; navigate to a new page with another 15s timer.
  5) After second timer completes, the final "تحميل" button appears → leads to direct URL.

- Variant B (short-circuit via internal link/state):
  - After entering the ArabSeed server flow, an internal link like `.../category/downloadz/?r=...&asd7b=1` appears.
  - Clicking it may bypass the second timer and directly reveal a "تحميل" anchor with final `.mp4` URL.
  - This likely depends on cookies, query params (e.g., `asd7b=1`), or prior interaction.

### Ads and Popups Behavior
- Common pattern: clicking "التحميل الان" or the first post-timer button opens an ad in a new tab (e.g., `obqj2.com`, Alibaba, other ad networks).
- Automation rule: close any newly opened tab whose domain matches an ad domain list, then retry the click on the original tab.
- Keep focus in the original tab for the actual progression.

### Timers
- Countdowns render before enabling the main button. Button appears or becomes enabled after ~15s.
- Strategies:
  - Wait for visible timer to complete by polling DOM text or by waiting for the target button to be enabled/visible.
  - Guard against early clicks that only open ad tabs; implement a retry once focus is back.

### Network and URL Patterns
- ArabSeed server link on quality list is Base64-wrapped via `a.asd.homes/l/<base64>`, decoding to something like `https://m.reviewrate.net/...` which then funnels into the site’s download flow.
- Intermediate landing page: `https://a.asd.homes/category/downloadz/?r=<id>` with optional `&asd7b=1` when short-circuiting.
- Final direct media link example (observed):
  - `https://fhd2k205.dls4all.online/d/<token>/[arabseed].High.Potential.S02E05.720p.mp4`
- Expect host/`<token>` to change per request; treat as dynamic.

### Headers and Downloading
- Some hosts require `Referer: https://a.asd.homes/` for direct download requests.
- Honor cookies from the flow when fetching the final URL programmatically if the host checks session.

### Automation Tactics (Playwright)
- Navigation and waits:
  - Prefer clicking by role+name for Arabic-labeled buttons/links.
  - Use `waitForNavigation` when a click is expected to navigate; otherwise, wait for target locator to be attached and visible/enabled.
- Tab/ad handling:
  - After click, check for new pages via `context.waitForEvent('page')` with a short timeout.
  - If a new page appears and its URL hostname is in an ad list, close it and refocus original page.
  - If no legitimate navigation occurred, retry the click once.
- Timers:
  - Poll for countdown completion by waiting for the target button to be enabled/visible.
  - Use a generous timeout (≥ 30s) for each timer step.
- Final URL capture:
  - First, look for a visible anchor with text "تحميل" and extract `href`.
  - Additionally, capture network requests that match `\.(mp4|m3u8)(\?|$)`.

### Suggested Ad Domain List (seed)
- `obqj2.com`, `68s8.com`, `cm65.com` and similar ad/tracker hosts.
- Maintain a configurable block/close list.

### Resilient Locator Examples
```ts
// Expand 720p
await page.getByText('تحميل بجودة 720p', { exact: false }).click();

// Choose ArabSeed direct server
await page.getByRole('link', { name: /سيرفر\s+عرب\s+سيد\s+المباشر/ }).click();

// First-step button (either link or button)
await page.getByRole('button', { name: 'التحميل الان' }).or(
  page.getByRole('link', { name: 'التحميل الان' })
).first().click();

// Intermediate/final step button
await page.getByRole('button', { name: 'اضغط للتحميل' }).click();

// Final direct link
const direct = await page.getByRole('link', { name: 'تحميل', exact: true }).getAttribute('href');
```

### Pseudocode for Full Variant Handling
```ts
// 1) Navigate → search → episode → /download page
// 2) Expand 720p and click ArabSeed server
// 3) Handle first timer page
await waitForTimerOrButton(page, 'اضغط للتحميل');
await clickWithAdRetry(context, page, page.getByRole('button', { name: 'اضغط للتحميل' }));

// 4) If navigated to new intermediate page with another timer
if (await page.getByRole('button', { name: 'اضغط للتحميل' }).count()) {
  await waitForTimerOrButton(page, 'اضغط للتحميل');
  await clickWithAdRetry(context, page, page.getByRole('button', { name: 'اضغط للتحميل' }));
}

// 5) Capture final link
const finalLink = await tryGetDirectLinkOrFromNetwork(page);
```

### Helper Behaviors
- `clickWithAdRetry`:
  - Click target → if new page opens and hostname is ad → close → click target again.
- `waitForTimerOrButton`:
  - Wait until target button is enabled/visible or countdown element disappears/changes.
- `tryGetDirectLinkOrFromNetwork`:
  - Prefer DOM `a[role=link][name=تحميل]` → fallback to last matching network `*.mp4|*.m3u8`.

### Known Differences (Your findings vs. this run)
- Your run consistently showed two 15s timers and an ad-tab between clicks before the final button.
- This run sometimes surfaced an internal link `?asd7b=1` that skipped the second timer and revealed a direct link immediately.
- We must support both paths in automation.

### Open Questions / Edge Cases
- Does the host occasionally switch to HLS (`.m3u8`) for some qualities?
- Are there geo or time-based changes in ad domains or required headers?
- Should we always prefer DOM-captured final link over network interception for stability?

### Actionable Implementation Notes
- Always choose the ArabSeed server entry in the 720p section.
- Expect at least one ad-tab; close and retry.
- Implement a two-timer flow with retries, plus a short-circuit path if `?asd7b=1` appears.
- Capture final URL and persist with the originating referer for later download.

### Identify Series vs Movie and Extract Episodes
- High signal DOM cues:
  - Series: presence of a heading containing "الحلقات" or "المواسم" and an adjacent list/grid of episode links titled like "الحلقة N".
  - Movie: no such heading and no links matching "الحلقة N".
  - Title heuristic: pages often start with "مسلسل ..." for series and "فيلم ..." for movies.

- Series detection (Playwright):
```ts
const isSeries = await page.evaluate(() =>
  Array.from(document.querySelectorAll('h2,h3,h4'))
    .some(h => /الحلقات|المواسم/.test((h.textContent || '').trim()))
);
```

- Episode extraction when series:
```ts
const episodes = await page.evaluate(() => {
  const heading = Array.from(document.querySelectorAll('h2,h3,h4'))
    .find(h => /الحلقات|المواسم/.test((h.textContent || '').trim()));
  if (!heading) return [] as { text: string; href: string }[];
  const container = heading.parentElement?.nextElementSibling || heading.closest('section,div');
  if (!container) return [] as { text: string; href: string }[];
  return Array.from(container.querySelectorAll('a'))
    .filter(a => /^\s*الحلقة\s*\d+\s*$/.test((a.textContent || '').trim()))
    .map(a => ({ text: (a.textContent || '').trim(), href: (a as HTMLAnchorElement).href }));
});
```

- Optional JSON-LD fallback:
```ts
const schemaType = await page.evaluate(() => {
  const el = document.querySelector('script[type="application/ld+json"]');
  if (!el) return null as string | null;
  try {
    const data = JSON.parse(el.textContent || '{}');
    const type = Array.isArray(data) ? data[0]?.['@type'] : data['@type'];
    return typeof type === 'string' ? type : null;
  } catch { return null; }
});
// Treat schemaType in { 'TVSeries', 'TVEpisode' } as series; 'Movie' as movie.
```


