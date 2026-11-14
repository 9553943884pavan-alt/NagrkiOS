> **Historical record:** This document describes an earlier version. For the current implementation use `AUDIT_V4.md`, `SECURITY.md` and `VALIDATION_V4.md`.

# v2 changelog — targeted fixes, no redesign

## UI

- Replaced heavy bright-green input/keyboard focus outlines with a subtle, still-visible focus treatment. Retained original dark teal sidebar, gradients, typography, cards and charts.
- Speech recognition now displays **interim words live**, updates a single transcript without duplication, and waits for the late final result when Stop is pressed. Added messages for no speech, unavailable network speech service, denied permissions and unsupported language. Browser speech services remain an experimental external dependency.
- Corrected misleading "All cases" highlight when other registry filters are active.
- Admin's assignment dropdown now shows officers from the selected department, clears stale assignees when department changes.
- Added a distinct **Department Officer dashboard** (department KPIs, assigned-to-me cases, priority queue), kept Admin global dashboard and Citizen portal. Officer nav no longer advertises global views or citizen grievance filing.

## Backend

- Opaque server-revocable session cookies with CSRF guard replace bearer tokens in JS storage.
- scrypt password hashes with random salts, login rate limits and legacy hash upgrades.
- Department-scoped officer reads, modifications and assignee listings; admin-only global analytics/export; secure assignment-to-department rules.
- Private uploaded-image ownership: random path and server-side claim, case-scoped read, non-reusable attachments; mock filename hints use stored upload name rather than trusting client content.
- Session invalidation on reset; private notes never exposed to citizens; admin can reset synthetic sandbox.
- Safe CSV values, basic HTTP hardening, secure-delete SQLite and file permissions on POSIX.

## Verified

- 19 backend tests pass; backend compiles; fallback JS passes syntax; all 18 TS/TSX source files pass syntax parsing.
- React production build and interactive browser E2E **not verified in this environment** (npm registry/network restrictions). See `VALIDATION.md`.
