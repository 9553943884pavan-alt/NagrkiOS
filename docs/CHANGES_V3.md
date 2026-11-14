> **Historical record:** This document describes an earlier version. For the current implementation use `AUDIT_V4.md`, `SECURITY.md` and `VALIDATION_V4.md`.

# v3 — Interaction quality and dependency maintenance

This is a **small frontend-only refinement** layered on top of the secured v2 backend. The dashboard cards, chart layouts, spacing system, palette, typography, data model, security rules, and account permissions were **not redesigned**.

## Changes

1. Introduced `frontend/src/components/SelectMenu.tsx`: shared accessible dropdown, clickable label **and** chevron, selected-state check, hover highlight, smooth opening, outside-click dismissal, Escape/Enter/arrow/Home/End/Tab navigation, automatic upward positioning when needed, and searchable choices for districts and longer department lists. The menu is displayed in a portal so clipped parent panels and tables cannot hide the choices.
2. Replaced React native dropdowns across the grievance registry, intelligence chart category, case edit controls (status/priority/department/owner), grievance submission district, and speech language selection.
3. Updated `frontend/src/styles.css` with scoped styling for the new dropdowns. The existing NagrikOS appearance is preserved.
4. Prevented the rectangular inner search-input focus ring on mouse clicks. Added a subtle field border on pointer focus, while preserving a visible small focus outline during keyboard navigation. The input-mode tracking is implemented in `frontend/src/main.tsx`.
5. Updated `frontend/package.json` to **Recharts 3.10.1** to avoid the deprecated 2.x branch. The chart components use standard documented APIs; interactive visual verification of this major upgrade is still required on the laptop.
6. Added a version-specific `allowScripts` approval for `esbuild@0.25.12` as observed in the installation warning. **If a later Vite resolution installs a different `esbuild` version**, review and approve that specific version using `npm approve-scripts esbuild`; do not enable all scripts blindly.

## Why this was necessary

The old filter UI used `<select>` and a **separate SVG chevron**, so clicking the chevron itself did not reliably open the native list. Native Windows Chromium menus also did not match the visual system. The old global input `:focus` box shadow caused the thin rectangular box inside the grievance search field. The shared component and focus rules solve these problems at their sources.

## Not changed

- Python backend/API, SQLite schema, role-based access controls, authentication, seeded data, fake ML inference, and image upload rules.
- Existing page design, navigation structure, and workflows.
- Backend-served low-dependency fallback UI on port 8000 (still uses native dropdowns). **These refinements apply to the React UI on port 5173.**

## Validation status

- Backend: **19 tests passed**, with no backend code changes.
- Frontend: **18 TS/TSX files syntax-parsed successfully** using TypeScript's `transpileModule`. This is **not** a full typecheck.
- Native `<select>` usages in the React application: **zero**.
- CSS: parsed with no stylesheet syntax errors.
- Headless Chromium computed-style smoke test: clicking the search field shows **no inner box shadow or outline**, and keyboard Tab navigation produces a visible compact outline.
- **Not verified:** full `npm install` / Recharts 3 type check / Vite build and functional React browser interactions. The npm registry was unreachable from the creation environment (`EAI_AGAIN`); these checks must be run on your laptop after `npm install`.

## Laptop manual regression checklist

1. **Admin / Grievances:** Click directly on the Status, Priority, and District **arrows**. Menus should open. Check selections filter the real list; search for Lucknow in the district dropdown. Click outside, press Escape, and select items with arrow keys + Enter.
2. **Search field:** Click into the grievance search box and type a ticket number; there should be no ugly thin box *inside* the input. Hit Tab and verify keyboard focus has a small, visible outline.
3. **Citizen / New grievance:** Open the District and Speech language menus. Type a district in the searchable list; check that preview and submit work with the chosen district. Voice transcription still depends on the browser speech service.
4. **Officer / Case details:** Open status, priority, and case owner arrows; save changes and verify persistence. An officer must not be able to change department or view another department's grievances.
5. **Admin / Intelligence:** Change category using the new dropdown, confirm chart updates. Check the Overview chart, donut, and other charts after the Recharts 3 upgrade.
6. **Mobile/short viewport:** Open a dropdown near the bottom of the page. It should open upward when there is insufficient space below, not be cut off by the panel.
7. **Windows PowerShell:** `cd frontend; npm install; npm run build; npm ls recharts esbuild; npm approve-scripts --allow-scripts-pending` and resolve any reported items before demo.
