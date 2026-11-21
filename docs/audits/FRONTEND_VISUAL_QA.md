# Frontend visual and interaction QA

**Date:** 21 November 2026. The existing design palette and layout were retained. Browser fixtures used synthetic account/case data or the unauthenticated login page; no production credentials appeared in screenshots.

## Confirmed and repaired

| Finding | Before | After | Evidence |
| --- | --- | --- | --- |
| 320 px login overflow (F-03) | `body{min-width:360px}` yielded `document.scrollWidth=360` at viewport 320 | Minimum width 320; `scrollWidth=320` | [Before](../../frontend/qa-artifacts/login-320-before.png), [after](../../frontend/qa-artifacts/login-320-after.png) |
| 320 px New Grievance overflow (F-08) | Independent isolated demo check measured `document.scrollWidth=326` at viewport 320; `.voice-actions` extended to x=326 | Voice controls wrap at narrow widths; document width 320 at viewport 320 | [Before](../../frontend/qa-artifacts/new-320-before-independent.png), [after](../../frontend/qa-artifacts/new-320-after.png); `frontend/tests/new-viewport-smoke.js` |
| Officer case-list action (F-04) | “New grievance” button sent officers to a route that redirects home | Action hidden for officers | Synthetic Playwright case smoke |
| All cases filter (F-04) | Cleared status but retained search/priority/district | Clears complete query and search input | Synthetic Playwright case smoke |
| Stale case results (F-04) | Earlier slow response could replace newer search results | Effect cleanup ignores stale result | Synthetic delayed/fast API fixture |
| Table keyboard access (F-04) | Focusable row with JavaScript Enter handling | Named native ticket link | Synthetic keyboard Enter smoke |

The local login after fix had no document overflow at 320, 375, 768, 1280 and 1920 px in the frontend specialist's Chromium checks. The New Grievance synthetic browser check passed at 320, 390, 768 and 1024 px. Independent QA also observed the original hosted login overflow at 320 px before the local change. The hosted site remains on the old build until a separately approved deployment.

## Performance evidence

| Build | Initial HTML-referenced JavaScript, gzip | Chart loading behavior |
| --- | ---: | --- |
| Baseline | 247.52 KB (index 117.38 KB + preloaded charts 130.14 KB) | Chart chunk preloaded for every visitor |
| Local fix | 117.65 KB (index only) | Chart code loaded through dynamic admin page imports |

The local build emitted an index bundle of 388.52 KB / 117.65 KB gzip, a shared BarChart chunk of 389.86 KB / 113.09 KB gzip, Overview 42.64 KB / 13.20 KB gzip, and Insights 31.72 KB / 10.49 KB gzip. These are bundle sizes, not observed transfer times or Core Web Vitals. LCP, INP and CLS were not measured, and no field percentile claim is made. The change removes initial chart preload for non-admin routes while retaining chart functionality in the built application.

## Coverage and limits

- Frontend specialist: Chromium login width checks and a synthetic officer `/cases` browser smoke covering four interactions.
- Independent QA: Chromium hosted login width check and isolated demo citizen dashboard, cases and New Grievance routes at 320 px; it discovered the New Grievance voice-control overflow. The independent before screenshot was retained. The final after check used synthetic API fixtures in the same browser engine.
- Route inventory was reviewed in `frontend/src/App.tsx`, but every modal, role, error/loading state, long-text case, zoom level, and mobile dashboard was not exhaustively inspected.
- Firefox, WebKit, automated axe scan, screen reader, and formal WCAG 2.2 AA conformance were not tested. Keyboard coverage is limited to the ticket link and focused smoke paths.
- Visual screenshots are before/after evidence for the confirmed login defect; no visual regression baseline exists for all routes.

See [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and [Playwright visual comparison guidance](https://playwright.dev/docs/test-snapshots) for the target criteria and stable screenshot practices.
