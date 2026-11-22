# Frontend visual and interaction QA

**Date:** 21 November 2026. The existing design palette and layout were retained. Browser fixtures used synthetic account/case data or the unauthenticated login page; no production credentials appeared in screenshots.

## Follow-up review, 22 November 2026

Chromium loaded **112 synthetic authenticated role/route/width combinations** (citizen 5 routes, officer 4, admin 7; widths 320, 375, 390, 768, 1024, 1440 and 1920 px) with zero settled document overflow. Six anonymous account screens loaded at the same seven widths (**42 checks**) with zero overflow. The final axe-core 4.10.3 WCAG 2 A/AA/2.1 AA rule scan at 390 px reported **zero violations across all 16 authenticated and six anonymous tested states**. Before the targeted color changes, all 16 authenticated states had serious contrast violations (7–25 nodes each), while six anonymous screens had 5–7 affected nodes each. A representative four-route authenticated contrast sample fell from 76 affected nodes to zero after fixes. This scan does not establish full WCAG conformance at all widths, states or assistive technologies.

The mobile closed sidebar previously remained keyboard-focusable while off screen. It is now inert and hidden from accessibility APIs when closed; opening moves focus into the menu, Tab stays inside it, Escape returns focus to the trigger, and the main area is inert while it is open. The department directory now uses native links, and its search field, the complaint photo input and case notes have accessible names. The synthetic keyboard regressions passed. [Synthetic mobile menu screenshot](../../frontend/qa-artifacts/mobile-nav-390-synthetic.png) and [admin dashboard screenshot](../../frontend/qa-artifacts/admin-overview-1440-synthetic.png) contain no production identities. The dashboard fixture uses the backend's `YYYY-MM` month shape.

The anonymous matrix exposed a same-tab token-link defect: the login module read the initial URL fragment only once, so following a reset, verification or invitation link after another account screen could leave the old form visible and submit a stale token. `Login.tsx` now handles fragment changes and reads the current token at submission. A local Playwright test exercised all three flows with mocked API responses, confirmed the current synthetic token each time, and checked hash removal and late-response behavior. No real account action occurred.

The final local build's index bundle is **118.27 KB gzip**, versus **117.65 KB** in the previous audit build and 247.52 KB before the first chart-loading fix. An earlier warm, local, synthetic Chromium sample on admin Overview at 1440 px measured FCP 208 ms, LCP 812 ms and CLS 0.0263. These are one-run lab values, not hosted or field Core Web Vitals. Firefox could not start on this Windows host because `lgpllibs.dll` was unavailable, and WebKit was not installed; neither engine passed a test.

## Confirmed and repaired

| Finding | Before | After | Evidence |
| --- | --- | --- | --- |
| 320 px login overflow (F-03) | `body{min-width:360px}` yielded `document.scrollWidth=360` at viewport 320 | Minimum width 320; `scrollWidth=320` | [Before](../../frontend/qa-artifacts/login-320-before.png), [after](../../frontend/qa-artifacts/login-320-after.png) |
| 320 px New Grievance overflow (F-08) | Independent isolated demo check measured `document.scrollWidth=326` at viewport 320; `.voice-actions` extended to x=326 | Voice controls wrap at narrow widths; document width 320 at viewport 320 | [Before](../../frontend/qa-artifacts/new-320-before-independent.png), [after](../../frontend/qa-artifacts/new-320-after.png); `frontend/tests/new-viewport-smoke.js` |
| Officer case-list action (F-04) | “New grievance” button sent officers to a route that redirects home | Action hidden for officers | Synthetic Playwright case smoke |
| All cases filter (F-04) | Cleared status but retained search/priority/district | Clears complete query and search input | Synthetic Playwright case smoke |
| Stale case results (F-04) | Earlier slow response could replace newer search results | Effect cleanup ignores stale result | Synthetic delayed/fast API fixture |
| Table keyboard access (F-04) | Focusable row with JavaScript Enter handling | Named native ticket link | Synthetic keyboard Enter smoke |

The local login after fix had no document overflow at 320, 375, 768, 1280 and 1920 px in the original Chromium checks. The New Grievance synthetic browser check passed at 320, 390, 768 and 1024 px. Independent QA also observed the original hosted login overflow at 320 px before the local change. The operator later authorized the audit-fix push; the hosted site subsequently served the matching release-build asset. Follow-up browser and accessibility evidence is recorded below.

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
- The original pass did not test Firefox, WebKit or axe. The follow-up added the Chromium matrix and axe checks above; Firefox/WebKit, screen readers, formal WCAG 2.2 AA conformance, all modal/error states, zoom and long text remain unverified.
- Visual screenshots are before/after evidence for the confirmed login defect; no visual regression baseline exists for all routes.

See [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and [Playwright visual comparison guidance](https://playwright.dev/docs/test-snapshots) for the target criteria and stable screenshot practices.
