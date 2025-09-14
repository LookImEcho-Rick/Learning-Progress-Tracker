# Changelog

## [Unreleased]
- Nothing yet.

## [0.0.1] - 2025-09-14
- Project initialized with documentation scaffolding.
- Core data model defined in `ARCHITECTURE.md`.
- Roadmap established.
- Implemented core app with local SQLite persistence.
- Added history view, insights (charts), and weekly summary.
- Implemented CSV export.
- Added week index calculation and weekly summary based on first entry.
- Added best-effort daily backups to `data/backups/`.
- Introduced pytest suite with storage and week-index tests.
- Added tags support and tag-based filtering in History.
- Added streaks (current, longest) and weekly goal metric with Settings page.
- Added editing and deletion of past entries in History.
- Added basic input validation for minutes, topic, and confidence.
- Added CSV import with background validation and simple Import/Export CSV UX.
- Removed Excel export and simplified Data page.
- Strengthened validation: max lengths, tag limits, and consistent sanitization across import and forms.
- Added import dry-run under the hood to validate before saving.
- Added automatic CSV sync at launch and exit to user Documents folder.
